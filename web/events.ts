import { ContextInputEvent, ContextInputEventDescriptor } from "./types";

const eventPrefix = "rxxxt-on-";
const now = () => new Date().getTime();

type TargetEvent = {
    // unique id
    submitId: number; // id for data

    // description
    descriptor: ContextInputEventDescriptor;
    event: string;
    tag: string; // local or global

    // state
    timeoutHandle?: number;
    lastCall?: number;

};

type EventHandler = (e: Event) => void;

const descriptorKeyCache = new WeakMap<ContextInputEventDescriptor, string>();
function descriptorKey(d: ContextInputEventDescriptor) {
    let key = descriptorKeyCache.get(d);
    if (key === undefined) {
        key = JSON.stringify([ d.context_id, d.handler_name, d.options.debounce ?? null, d.options.prevent_default ?? null,
            d.options.throttle ?? null, ...Object.entries(d.param_map).sort((a, b) => a[0].localeCompare(b[0])) ]);
        descriptorKeyCache.set(d, key);
    }
    return key;
}

function getLocalElementEventDescriptors(element: Element) {
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

/**
 * This is very messy ... a lot of bad choices.
 */
export function initEventManager(triggerUpdate: () => void) {
    let submitIdCounter = 0;
    const targetEvents = new WeakMap<EventTarget, TargetEvent[]>();
    const registeredTargetEvents = new WeakMap<EventTarget, Map<string, EventHandler>>();
    const eventDataSubmissions = new Map<number, ContextInputEvent>(); // preserves insertion order. Important!
    const enabledContexts = new Set<string>();


    const eventHandler = (target: EventTarget, e: Event) => {
        let peningEvents = targetEvents.get(target) ?? [];
        const newEvents = peningEvents.filter(e => enabledContexts.has(e.descriptor.context_id));
        if (newEvents.length !== peningEvents.length) {
            targetEvents.set(target, newEvents);
            updateHandlers(target);
            peningEvents = newEvents;
        }

        for (const targetEvent of peningEvents.filter(te => te.event === e.type)) {
            const eventData: Record<string, number | boolean | string | undefined> = {
                $handler_name: targetEvent.descriptor.handler_name,
                ...(targetEvent.descriptor.options.default_params ?? {}),
                ...Object.fromEntries(Object.entries(targetEvent.descriptor.param_map)
                    .map(entry => [entry[0], getEventPathValue(e, entry[1])]))
            };

            eventDataSubmissions.set(targetEvent.submitId, {
                context_id: targetEvent.descriptor.context_id,
                data: eventData
            });

            if (targetEvent.timeoutHandle) {
                clearTimeout(targetEvent.timeoutHandle);
                targetEvent.timeoutHandle = undefined;
            }

            if (targetEvent.descriptor.options.prevent_default) {
                e.preventDefault();
            }

            if (!targetEvent.descriptor.options.no_trigger) {
                const waitTime = Math.max(
                    0,
                    targetEvent.descriptor.options.debounce ?? 0,
                    (targetEvent.lastCall ?? 0) + (targetEvent.descriptor.options.throttle ?? 0) - now()
                );

                targetEvent.timeoutHandle = setTimeout(() => {
                    if (eventDataSubmissions.has(targetEvent.submitId)) {
                        targetEvent.lastCall = now();
                        triggerUpdate();
                    }
                }, waitTime);
            }
        }
    };

    const updateHandlers = (target: EventTarget) => {
        const reg = registeredTargetEvents.get(target) ?? new Map<string, EventHandler>();
        registeredTargetEvents.set(target, reg);

        const newReg = new Set(targetEvents.get(target)?.map(e => e.event) ?? []);
        for (const event of Array.from(reg.keys())) {
            if (!newReg.has(event)) {
                target.removeEventListener(event, reg.get(event)!);
                reg.delete(event);
            }
        }

        for (const event of newReg) {
            if (!reg.has(event)) {
                const newHandler = (e: Event) => eventHandler(target, e);
                target.addEventListener(event, newHandler);
                reg.set(event, newHandler);
            }
        }
    };

    const popPendingEvents = () => {
        const res = Array.from(eventDataSubmissions.values());
        eventDataSubmissions.clear();
        return res;
    };
    const onElementUpdated = (element: Element) => {
        if (element.tagName === "RXXXT-META") {
            enabledContexts.add(element.id)
        }

        const registeredLocalEvents = new Map((targetEvents.get(element) ?? []).filter(e => e.tag == "local").map(e => [e.event, e]));
        const newEventDescriptors = getLocalElementEventDescriptors(element);

        for (const targetEvent of registeredLocalEvents.values()) {
            if (!newEventDescriptors.has(targetEvent.event)) {
                unregisterEvent(element, targetEvent.event, targetEvent.descriptor, "local");
            }
        }

        for (const newEventEntry of newEventDescriptors.entries()) {
            if (registeredLocalEvents.has(newEventEntry[0])) {
                registeredLocalEvents.get(newEventEntry[0])!.descriptor = newEventEntry[1];
            }
            else {
                registerEvent(element, newEventEntry[0], newEventEntry[1], "local");
            }
        }
    };
    const onElementDeleted = (element: Element) => {
        if (element.tagName === "RXXXT-META") {
            enabledContexts.delete(element.id)
        }
    }
    const registerEvent = (target: EventTarget, event: string, descriptor: ContextInputEventDescriptor, tag: string = "global") => {
        const key = descriptorKey(descriptor);
        const elementEvents = targetEvents.get(target) ?? [];
        targetEvents.set(target, elementEvents);

        let regEvent = elementEvents.find(e => e.event === event && descriptorKey(e.descriptor) === key && e.tag == tag);
        if (regEvent === undefined) {
            elementEvents.push({ descriptor, event, submitId: ++submitIdCounter, tag: tag });
        }
        else {
            regEvent.descriptor = descriptor;
        }

        updateHandlers(target);
    };
    const unregisterEvent = (target: EventTarget, event: string, descriptor: ContextInputEventDescriptor, tag: string = "global") => {
        const key = descriptorKey(descriptor);
        targetEvents.set(target, (targetEvents.get(target) ?? []).filter(e => e.event != event || descriptorKey(e.descriptor) !== key || e.tag !== tag));
        updateHandlers(target);
    };

    return { registerEvent, unregisterEvent, onElementUpdated, onElementDeleted, popPendingEvents };
}
