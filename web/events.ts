import { InputEvent, InputEventDescriptor } from "./types";

const eventPrefix = "rxxxt-on-";
const now = () => new Date().getTime();

class RegisteredEvent {
    private static submitIdCounter = 0;

    public descriptorRaw: string;
    public handler: (e: Event) => void;

    private readonly submitId: number;
    private readonly triggerCallback: () => void;
    private readonly submitMap: Map<number, InputEvent>;

    private get descriptor() {
        return JSON.parse(atob(this.descriptorRaw)) as InputEventDescriptor;
    }

    private timeoutHandle?: number;
    private lastCall?: number;

    constructor(triggerCallback: () => void, submitMap: Map<number, InputEvent>, descriptorRaw: string) {
        this.triggerCallback = triggerCallback;
        this.descriptorRaw = descriptorRaw;
        this.handler = this.handle.bind(this);
        this.submitMap = submitMap;
        this.submitId = ++RegisteredEvent.submitIdCounter;
    }

    private handle(e: Event) {
        const eventData: Record<string, number | boolean | string | undefined> = {
            ...(this.descriptor.options.default_params ?? {}),
            ...Object.fromEntries(Object.entries(this.descriptor.options.param_map ?? {})
                .map(entry => [entry[0], getEventPathValue(e, entry[1])]))
        };

        this.submitMap.set(this.submitId, {
            context_id: this.descriptor.context_id,
            data: eventData
        });

        if (this.timeoutHandle) {
            clearTimeout(this.timeoutHandle);
            this.timeoutHandle = undefined;
        }

        if (this.descriptor.options.prevent_default) {
            e.preventDefault();
        }

        if (!this.descriptor.options.no_trigger) {
            const waitTime = Math.max(
                0,
                this.descriptor.options.debounce ?? 0,
                (this.lastCall ?? 0) + (this.descriptor.options.throttle ?? 0) - now()
            );

            this.timeoutHandle = setTimeout(() => {
                if (this.submitMap.has(this.submitId)) {
                    this.lastCall = now();
                    this.triggerCallback();
                }
            }, waitTime);
        }
    }
}

function getLocalElementEventDescriptors(element: Element)  {
    const res = new Map<string, string>();

    for (const attributeName of element.getAttributeNames()) {
        if (attributeName.startsWith(eventPrefix)) {
            const eventName = attributeName.substring(eventPrefix.length);
            const rawDescriptor = element.getAttribute(attributeName);
            if (rawDescriptor !== null) {
                res.set(eventName, rawDescriptor);
            }
        }
    }

    return res;
}

function getEventPathValue(event: Event, path: string) {
    let value = event as any; // any needed for typing...
    try {
        for (const part of path.split(".")) {
            value = value[part];
        }
        if (typeof value == "string" || typeof value == "number" || typeof value == "boolean") {
            return value;
        }
        else {
            return undefined;
        }
    }
    catch {
        return undefined;
    }
}

export function initEventManager(triggerUpdate: () => void) {
    const targetRegisteredEvents = new WeakMap<EventTarget, Map<string, RegisteredEvent>>();
    const submitMap = new Map<number, InputEvent>();

    const popPendingEvents = () => {
        const result = new Map(submitMap);
        submitMap.clear();
        return result;
    };
    const onElementUpdated = (element: Element) => {
        const newEventDescriptors = getLocalElementEventDescriptors(element);
        const registeredEvents = targetRegisteredEvents.get(element) ?? new Map<string, RegisteredEvent>();
        targetRegisteredEvents.set(element, registeredEvents);

        for (const registeredEventName of registeredEvents?.keys()) {
            if (!newEventDescriptors.has(registeredEventName)) {
                element.removeEventListener(registeredEventName, registeredEvents.get(registeredEventName)!.handler);
                registeredEvents.delete(registeredEventName);
            }
        }

        for (const item of newEventDescriptors.entries()) {
            const registeredEvent = registeredEvents.get(item[0]);
            if (registeredEvent === undefined) {
                const newRegisteredEvent = new RegisteredEvent(triggerUpdate, submitMap, item[1]);
                element.addEventListener(item[0], newRegisteredEvent.handler);
                registeredEvents.set(item[0], newRegisteredEvent);
            }
            else {
                registeredEvent.descriptorRaw = item[1];
            }
        }
    };

    return { onElementUpdated, popPendingEvents };
}
