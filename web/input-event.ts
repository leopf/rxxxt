import objectPath from "object-path";
import {
    ContextCleanable,
    ContextInputEvent,
    ContextInputEventDescriptor,
} from "./types";

function getContextInputEventDescriptorId(d: ContextInputEventDescriptor) {
    return JSON.stringify([
        d.context_id,
        d.handler_name,
        d.options.debounce ?? null,
        d.options.prevent_default ?? null,
        d.options.throttle ?? null,
        ...Object.entries(d.param_map).sort((a, b) => a[0].localeCompare(b[0])),
    ]);
}

export type EventUpdater = (prod: ContextEventHandler) => void;

export class ContextEventHandler {
    private descriptor: ContextInputEventDescriptor;
    private lastCall?: number;
    private timeoutHandle?: number;
    private nextEvent?: ContextInputEvent;

    private updater: () => void;
    public handler = (e: Event) => this.handle(e);

    constructor(
        updater: EventUpdater,
        descriptor: ContextInputEventDescriptor,
    ) {
        this.descriptor = descriptor;
        this.updater = () => updater(this);
    }

    public get id() {
        return getContextInputEventDescriptorId(this.descriptor);
    }

    public popEvent() {
        if (this.timeoutHandle) {
            clearTimeout(this.timeoutHandle);
        }
        const result = this.nextEvent;
        if (this.nextEvent) {
            this.lastCall = new Date().getTime();
            this.nextEvent = undefined;
        }
        return result;
    }

    private handle(e: Event) {
        const eventData: Record<string, number | boolean | string> = {
            $handler_name: this.descriptor.handler_name,
        };

        for (const outField of Object.keys(this.descriptor.param_map)) {
            const eventField = this.descriptor.param_map[outField];
            eventData[outField] = objectPath.withInheritedProps.get(
                e,
                eventField,
            );
        }

        this.nextEvent = {
            context_id: this.descriptor.context_id,
            data: eventData,
        };

        if (this.timeoutHandle) {
            clearTimeout(this.timeoutHandle);
            this.timeoutHandle = undefined;
        }

        if (this.descriptor.options.prevent_default) {
            e.preventDefault();
        }

        const waitTimes: number[] = [];
        if (this.descriptor.options.debounce) {
            waitTimes.push(this.descriptor.options.debounce);
        }
        if (this.descriptor.options.throttle && this.lastCall) {
            const currTime = new Date().getTime();
            waitTimes.push(
                this.descriptor.options.throttle + this.lastCall - currTime,
            );
        }
        const waitTime = Math.max(0, ...waitTimes);

        if (waitTime === 0) {
            this.updater();
        } else {
            this.timeoutHandle = setTimeout(this.updater, waitTime);
        }
    }
}

const eventPrefix = "rxxxt-on-";

export class ElementEventManager {
    private updater: EventUpdater;
    private nodeHandlers = new WeakMap<
        Node,
        Record<string, ContextEventHandler>
    >();

    constructor(updater: EventUpdater) {
        this.updater = updater;
    }

    public apply(container: Element) {
        for (const element of container.getElementsByTagName("*")) {
            this.applyElement(element);
        }
    }

    private applyElement(element: Element) {
        const oldEventHandlers = new Map(
            Object.entries(this.nodeHandlers.get(element) ?? {}),
        );
        const newEventDescriptors = this.getEventDescriptors(element);
        const newEventHandlers: Record<string, ContextEventHandler> = {};

        for (const eventName of oldEventHandlers.keys()) {
            const eventHandler = oldEventHandlers.get(eventName)!;
            if (
                newEventDescriptors.has(eventName) &&
                getContextInputEventDescriptorId(
                    newEventDescriptors.get(eventName)!,
                ) == eventHandler.id
            ) {
                newEventDescriptors.delete(eventName);
                newEventHandlers[eventName] = eventHandler;
            } else {
                element.removeEventListener(eventName, eventHandler.handler);
            }
        }

        for (const eventND of newEventDescriptors.entries()) {
            const handler = new ContextEventHandler(this.updater, eventND[1]);
            element.addEventListener(eventND[0], handler.handler);
            newEventHandlers[eventND[0]] = handler;
        }

        this.nodeHandlers.set(element, newEventHandlers);
    }

    private getEventDescriptors(
        element: Element,
    ): Map<string, ContextInputEventDescriptor> {
        const res = new Map<string, ContextInputEventDescriptor>();

        for (const attributeName of element.getAttributeNames()) {
            if (attributeName.startsWith(eventPrefix)) {
                const eventName = attributeName.substring(eventPrefix.length);
                const eventDesc: ContextInputEventDescriptor = JSON.parse(
                    atob(element.getAttribute(attributeName) ?? ""),
                );
                res.set(eventName, eventDesc);
            }
        }

        return res;
    }
}

interface RegisteredGlobalEvent {
    handler: ContextEventHandler;
    name: string;
    target: WeakRef<EventTarget>;
}

export class GlobalEventManager implements ContextCleanable {
    private contextEvents = new Map<string, RegisteredGlobalEvent[]>();
    private updater: EventUpdater;

    constructor(updater: EventUpdater) {
        this.updater = updater;
    }

    public registerEvent(
        target: EventTarget,
        name: string,
        descriptor: ContextInputEventDescriptor,
    ) {
        const registeredEvents =
            this.contextEvents.get(descriptor.context_id) ?? [];
        if (
            registeredEvents.some(
                (e) =>
                    e.target.deref() == target &&
                    e.name == name &&
                    e.handler.id ==
                        getContextInputEventDescriptorId(descriptor),
            )
        ) {
            return;
        }

        const handler = new ContextEventHandler(this.updater, descriptor);
        target.addEventListener(name, handler.handler);

        registeredEvents.push({
            target: new WeakRef(target),
            name: name,
            handler: handler,
        });

        this.contextEvents.set(descriptor.context_id, registeredEvents);
    }
    public unregisterEvent(
        target: EventTarget,
        name: string,
        descriptor: ContextInputEventDescriptor,
    ) {
        const registeredEvents: RegisteredGlobalEvent[] = [];
        for (const e of this.contextEvents.get(descriptor.context_id) ?? []) {
            if (
                e.target.deref() == target &&
                e.name == name &&
                e.handler.id == getContextInputEventDescriptorId(descriptor)
            ) {
                this.removeEventHandler(e);
            } else {
                registeredEvents.push(e);
            }
        }

        if (registeredEvents.length == 0) {
            this.contextEvents.delete(descriptor.context_id);
        } else {
            this.contextEvents.set(descriptor.context_id, registeredEvents);
        }
    }
    public clean(ids: Set<string>) {
        for (const id of ids) {
            const events = this.contextEvents.get(id) ?? [];
            this.contextEvents.delete(id);
            events.forEach(this.removeEventHandler);
        }
    }

    private removeEventHandler(r: RegisteredGlobalEvent) {
        const target = r.target.deref();
        if (target !== undefined) {
            target.removeEventListener(r.name, r.handler.handler);
        }
    }
}
