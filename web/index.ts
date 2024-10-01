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
    event: "navigate",
    location: string
}

interface UpgradeWebsocketOutputEvent {
    event: "upgrade-websocket",
}

type OutputEvent = SetCookieOutputEvent | ForceRefreshOutputEvent | NavigateOutputEvent | UpgradeWebsocketOutputEvent;

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
    events: OutputEvent[]
}

let stateToken: string = "";
let enableStateUpdates: boolean = false;
let updateScheduled: boolean = false;
let updateRunning: boolean = false;
let updateHandler: () => void;
let updateSocket: WebSocket | undefined;
const inputEvents: ContextInputEvent[] = [];
const trackedElements = new WeakMap<Node, TrackedElement>();
const defaultTargetId = "razz-root";
const eventPrefix = "razz-on-";

const startUpdate = () => {
    updateRunning = true;
    updateScheduled = false;
};
const finishUpdate = () => {
    updateRunning = false;
    if (updateScheduled) {
        update();
    }
};

const handleOutputEvents = (events: OutputEvent[]) => {
    let refresh: boolean = false;
    for (const event of events) {
        if (event.event === "force-refresh") {
            refresh = true;
        }
        else if (event.event === "navigate") {
            window.history.pushState({}, "", event.location);
            refresh = true;
        }
        else if (event.event === "upgrade-websocket") {
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
        if (updateRoot === null || updateRoot.tagName !== "razz-meta".toUpperCase()) {
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
    if (!updateSocket) {
        return;
    }
    startUpdate();
    updateSocket = new WebSocket(location.href);
    updateSocket.addEventListener("close", () => {
        updateHandler = httpUpdateHandler;
    });
    updateSocket.addEventListener("open", () => {
        updateHandler = websocketUpdateHandler;
        updateSocket?.send(JSON.stringify({
            type: "init",
            state: stateToken,
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
        events: inputEvents,
        location: location.href.substring(location.origin.length)
    }));
};

const httpUpdateHandler = async () => {
    startUpdate();
    const body = JSON.stringify({
        stateToken,
        events: inputEvents
    });
    inputEvents.length = 0;

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
            if (!updateRunning) {
                updateHandler();
            }
        }, 0);
    }
};

class TrackedElementEvent {
    private lastCall?: number;
    private timeoutHandle?: number;
    public handler = (e: Event) => this.handle(e);

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

        const runEvent = () => {
            this.lastCall = (new Date()).getTime();
            inputEvents.push({
                context_id: eventDesc.context_id,
                data: eventData,
                handler_name: eventDesc.handler_name
            });
            update();
            this.timeoutHandle = undefined;
        };

        if (this.timeoutHandle) {
            clearTimeout(this.timeoutHandle);
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
            runEvent();
        }
        else {
            this.timeoutHandle = setTimeout(runEvent, waitTime);
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

(window as any).razzInit = (data: InitData) => {
    stateToken = data.stateToken;
    handleOutputEvents(data.events);
    applyHTML();
};