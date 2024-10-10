import morphdom from "morphdom";
import objectPath from "object-path";

interface SetCookieOutputEvent {
    event: "set-cookie"
    name: string
    value?: string
    expires?: string
    path?: string
    max_age?: number
    secure?: boolean
    http_only?: boolean
    domain?: string
}

interface ForceRefreshOutputEvent {
    event: "force-refresh"
}

interface NavigateOutputEvent {
    event: "navigate"
    location: string
}

interface UseWebsocketOutputEvent {
    event: "use-websocket"
    websocket: boolean
}

interface ContextInputEvent {
    context_id: string;
    handler_name: string;
    data: Record<string, number | string | boolean>;
}

interface ContextInputEventDescription {
    context_id: string;
    handler_name: string;
    param_map: Record<string, string>,
    options: {
        throttle?: number,
        debounce?: number,
        prevent_default?: boolean
    }
}

interface AppHttpPostResponse {
    stateToken: string,
    events: OutputEvent[]
    html: string
}

interface AppWebsocketResponse {
    stateToken?: string
    events: OutputEvent[]
    html: string
    end: boolean
}

interface InitData {
    stateToken: string,
    events: OutputEvent[],
    path: string
}

type OutputEvent = SetCookieOutputEvent | ForceRefreshOutputEvent | NavigateOutputEvent | UseWebsocketOutputEvent;
type InputEventProducer = () => ContextInputEvent[];

let baseUrl: URL | undefined;
let stateToken: string = "";
let enableStateUpdates: boolean = false;
let updateScheduled: boolean = false;
let updatesRunning: number = 0;
let updateHandler: () => void;
let updateSocket: WebSocket | undefined;
const inputEventProducers: InputEventProducer[] = [];
const trackedElements = new WeakMap<Node, TrackedElement>();
const defaultTargetId = "rxxxt-root";
const eventPrefix = "rxxxt-on-";

const startUpdate = () => {
    updatesRunning++;
    updateScheduled = false;
};
const finishUpdate = () => {
    updatesRunning = Math.max(0, updatesRunning - 1);
    if (updatesRunning == 0 && updateScheduled) {
        updateHandler();
    }
};

const produceInputEvents = () => {
    const events: ContextInputEvent[] = [];
    let producer: InputEventProducer | undefined;
    while (producer = inputEventProducers.shift()) {
        events.push(...producer());
    }
    return events;
};

const handleOutputEvents = (events: OutputEvent[]) => {
    let refresh: boolean = false;
    for (const event of events) {
        if (event.event === "force-refresh") {
            refresh = true;
        }
        else if (event.event === "navigate") {
            const targetUrl = new URL(event.location, location.href);
            if (baseUrl === undefined || baseUrl.origin !== targetUrl.origin || !targetUrl.pathname.startsWith(baseUrl.pathname)) {
                location.assign(targetUrl);
            }
            else {
                window.history.pushState({}, "", event.location);
                refresh = true;
            }
        }
        else if (event.event === "use-websocket" && event.websocket) {
            upgradeToWebsocket();
            refresh = true;
        }
        else if (event.event === "set-cookie") {
            const parts: string[] = [`${event.name}=${event.value ?? ""}`];
            if (typeof event.path === "string") {
                parts.push(`path=${event.path}`);
            }
            if (typeof event.expires === "string") {
                parts.push(`expires=${(new Date(event.expires)).toUTCString()}`);
            }
            if (typeof event.max_age === "number") {
                parts.push(`max-age=${event.max_age}`);
            }
            if (typeof event.domain === "string") {
                parts.push(`domain=${event.domain}`);
            }
            if (event.secure) {
                parts.push(`secure`);
            }
            if (event.http_only) {
                parts.push(`httponly`);
            }

            document.cookie = parts.join(";");
        }
    }

    if (refresh) {
        update();
    }
};

const applyHTML = (html?: string) => {
    let target: Element;

    if (html === undefined) {
        const ttarget = document.getElementById(defaultTargetId);
        if (ttarget === null) {
            throw new Error("Update target not found!");
        }
        target = ttarget;
    }
    else {
        const temp = document.createElement("div");
        temp.innerHTML = html;

        const updateRoot = temp.children.item(0);
        if (updateRoot === null || updateRoot.tagName !== "rxxxt-meta".toUpperCase()) {
            throw new Error("Invalid update root!");
        }

        const ttarget = document.getElementById(updateRoot.id);
        if (ttarget === null) {
            throw new Error("Update target not found!");
        }

        target = ttarget;
        morphdom(target, updateRoot);
    }

    for (const element of target.getElementsByTagName("*")) {
        let trackedElement = trackedElements.get(element);
        if (trackedElement === undefined) {
            trackedElement = new TrackedElement();
            trackedElements.set(element, trackedElement);
        }
        trackedElement.track(element);
    }
};

const upgradeToWebsocket = () => {
    if (updateSocket) {
        return;
    }
    startUpdate();
    const url = new URL(location.href);
    url.protocol = location.protocol == "https:" ? "wss" : "ws";
    updateSocket = new WebSocket(url);
    updateSocket.addEventListener("close", () => {
        updateHandler = httpUpdateHandler;
        updateSocket = undefined;
    });
    updateSocket.addEventListener("open", () => {
        updateHandler = websocketUpdateHandler;
        updateSocket?.send(JSON.stringify({
            type: "init",
            stateToken: stateToken,
            enableStateUpdates: enableStateUpdates
        }));
        finishUpdate();
    });
    updateSocket.addEventListener("message", (e) => {
        if (typeof e.data !== "string") {
            return;
        }

        const response: AppWebsocketResponse = JSON.parse(e.data);
        applyHTML(response.html);
        if (response.stateToken) {
            stateToken = response.stateToken;
        }
        handleOutputEvents(response.events);
        if (response.end) {
            finishUpdate();
        }
    });
};

const websocketUpdateHandler = async () => {
    startUpdate();
    updateSocket?.send(JSON.stringify({
        type: "update",
        events: produceInputEvents(),
        location: location.href.substring(location.origin.length)
    }));
};

const httpUpdateHandler = async () => {
    startUpdate();
    const body = JSON.stringify({
        stateToken,
        events: produceInputEvents()
    });

    const response: AppHttpPostResponse = await fetch(location.href, {
        method: "POST",
        body: body,
        headers: {
            "Content-Type": "application/json"
        },
        credentials: "include",
    }).then(res => res.json());

    applyHTML(response.html);
    stateToken = response.stateToken;
    handleOutputEvents(response.events);
    finishUpdate();
};
updateHandler = httpUpdateHandler;

const update = () => {
    if (!updateScheduled) {
        updateScheduled = true;
        setTimeout(() => {
            if (updatesRunning == 0) {
                updateHandler();
            }
        }, 0);
    }
};

class TrackedElementEvent {
    private lastCall?: number;
    private timeoutHandle?: number;
    private nextEvent?: ContextInputEvent;
    public handler = (e: Event) => this.handle(e);

    public produceEvent(): ContextInputEvent[] {
        if (this.timeoutHandle) {
            clearTimeout(this.timeoutHandle);
        }
        const result: ContextInputEvent[] = [];
        if (this.nextEvent) {
            this.lastCall = (new Date()).getTime();
            result.push(this.nextEvent);
            this.nextEvent = undefined;
        }
        return result;
    }

    private handle(e: Event) {
        if (e.target === null || !(e.target instanceof Element)) {
            return;
        }
        const targetAttribute = eventPrefix + e.type;
        const eventDescB64 = e.target.getAttribute(targetAttribute);

        if (eventDescB64 === null) {
            return;
        }

        const eventDesc: ContextInputEventDescription = JSON.parse(atob(eventDescB64));
        const eventData: Record<string, number | boolean | string> = {};

        for (const outField of Object.keys(eventDesc.param_map)) {
            const eventField = eventDesc.param_map[outField];
            eventData[outField] = objectPath.withInheritedProps.get(e, eventField);
        }

        this.nextEvent = {
            context_id: eventDesc.context_id,
            data: eventData,
            handler_name: eventDesc.handler_name
        };

        inputEventProducers.push(this.produceEvent.bind(this));

        if (this.timeoutHandle) {
            clearTimeout(this.timeoutHandle);
            this.timeoutHandle = undefined;
        }

        if (eventDesc.options.prevent_default) {
            e.preventDefault();
        }

        const waitTimes: number[] = [];
        if (eventDesc.options.debounce) {
            waitTimes.push(eventDesc.options.debounce);
        }
        if (eventDesc.options.throttle && this.lastCall) {
            const currTime = (new Date()).getTime();
            waitTimes.push(eventDesc.options.throttle + this.lastCall - currTime);
        }
        const waitTime = Math.max(0, ...waitTimes);

        if (waitTime === 0) {
            update();
        }
        else {
            this.timeoutHandle = setTimeout(update, waitTime);
        }
    }
}

class TrackedElement {
    private eventMap = new Map<string, TrackedElementEvent>();

    public track(element: Element) {
        const pendingEvents = new Set<string>();
        for (const attributeName of element.getAttributeNames()) {
            if (attributeName.startsWith(eventPrefix)) {
                const eventName = attributeName.substring(eventPrefix.length);
                pendingEvents.add(eventName);
            }
        }

        for (const entry of this.eventMap.entries()) {
            const eventName = entry[0];
            const event = entry[1];
            if (!pendingEvents.has(eventName)) {
                element.removeEventListener(eventName, event.handler);
                this.eventMap.delete(eventName);
            }
        }

        for (const eventName of pendingEvents) {
            if (!this.eventMap.has(eventName)) {
                const event = new TrackedElementEvent();
                this.eventMap.set(eventName, event);
                element.addEventListener(eventName, event.handler);
            }
        }
    }
}

(window as any).rxxxt = {
    navigate: (url: string | URL) => handleOutputEvents([ { event: "navigate", location: (new URL(url, location.href)).href } ]),
    init: (data: InitData) => {
        baseUrl = new URL(location.href);
        if (baseUrl.pathname.endsWith(data.path)) {
            baseUrl.pathname = baseUrl.pathname.slice(0, baseUrl.pathname.length - data.path.length)
        }
        else {
            console.warn("Invalid base url!")
        }

        window.addEventListener("popstate", update);
        stateToken = data.stateToken;
        handleOutputEvents(data.events);
        applyHTML();
    }
}