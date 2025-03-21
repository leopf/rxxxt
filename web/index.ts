import morphdom from "morphdom";
import {
    InputEventProducer,
    ContextInputEvent,
    OutputEvent,
    AppWebsocketResponse,
    AppHttpPostResponse,
    ContextInputEventDescriptor,
    InitData,
} from "./types";
import {
    ContextEventHandler,
    ElementEventManager,
    GlobalEventManager,
} from "./input-event";

let baseUrl: URL | undefined;
let stateToken: string = "";
let enableStateUpdates: boolean = false;
let updateHandler: () => void;
let updateSocket: WebSocket | undefined;
const defaultTargetId = "root";

const pendingContextEvents = new Set<ContextEventHandler>();
let updateScheduled: boolean = false;
let updatesRunning: number = 0;

const onPendingContextEvent = (e: ContextEventHandler) => {
    pendingContextEvents.add(e);
    update();
};

const elementEventManager = new ElementEventManager(onPendingContextEvent);
const globalEventManager = new GlobalEventManager(onPendingContextEvent);

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

const popInputEvents = () => {
    const events: ContextInputEvent[] = [];
    for (const pending of pendingContextEvents) {
        const event = pending.popEvent();
        if (event !== undefined) {
            events.push(event);
        }
    }
    pendingContextEvents.clear();
    return events;
};

const handleOutputEvents = (events: OutputEvent[]) => {
    for (const event of events) {
        if (event.event === "navigate") {
            const targetUrl = new URL(event.location, location.href);
            if (
                baseUrl === undefined ||
                baseUrl.origin !== targetUrl.origin ||
                !targetUrl.pathname.startsWith(baseUrl.pathname)
            ) {
                location.assign(targetUrl);
            } else {
                window.history.pushState({}, "", event.location);
            }
        } else if (event.event === "use-websocket") {
            if (event.websocket) {
                upgradeToWebsocket();
            } else {
                updateSocket?.close();
            }
        } else if (event.event === "set-cookie") {
            const parts: string[] = [`${event.name}=${event.value ?? ""}`];
            if (typeof event.path === "string") {
                parts.push(`path=${event.path}`);
            }
            if (typeof event.expires === "string") {
                parts.push(`expires=${new Date(event.expires).toUTCString()}`);
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
        } else if (event.event === "event-modify-window") {
            if (event.mode === "add") {
                globalEventManager.registerEvent(
                    window,
                    event.name,
                    event.descriptor,
                );
            } else if (event.mode === "remove") {
                globalEventManager.unregisterEvent(
                    window,
                    event.name,
                    event.descriptor,
                );
            }
        } else if (event.event === "event-modify-query-selector") {
            const elements: EventTarget[] = [];
            if (event.all) {
                elements.push(...document.querySelectorAll(event.selector));
            } else {
                const element = document.querySelector(event.selector);
                if (element !== null) {
                    elements.push(element);
                }
            }
            for (const element of elements) {
                if (event.mode === "add") {
                    globalEventManager.registerEvent(
                        element,
                        event.name,
                        event.descriptor,
                    );
                } else if (event.mode === "remove") {
                    globalEventManager.unregisterEvent(
                        element,
                        event.name,
                        event.descriptor,
                    );
                }
            }
        }
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
    } else {
        const temp = document.createElement("div");
        temp.innerHTML = html;

        const updateRoot = temp.children.item(0);
        if (
            updateRoot === null ||
            updateRoot.tagName !== "rxxxt-meta".toUpperCase()
        ) {
            throw new Error("Invalid update root!");
        }

        const ttarget = document.getElementById(updateRoot.id);
        if (ttarget === null) {
            throw new Error("Update target not found!");
        }

        target = ttarget;
        morphdom(target, updateRoot);
    }

    elementEventManager.apply(target);
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
        updateSocket?.send(
            JSON.stringify({
                type: "init",
                state_token: stateToken,
                enable_state_updates: enableStateUpdates,
            }),
        );
        finishUpdate();
    });
    updateSocket.addEventListener("message", (e) => {
        if (typeof e.data !== "string") {
            return;
        }

        const response: AppWebsocketResponse = JSON.parse(e.data);
        for (const part of response.html_parts) {
            applyHTML(part);
        }
        if (response.state_token) {
            stateToken = response.state_token;
        }
        handleOutputEvents(response.events);
        finishUpdate();
    });
};

const websocketUpdateHandler = async () => {
    startUpdate();
    updateSocket?.send(
        JSON.stringify({
            type: "update",
            events: popInputEvents(),
            location: location.href.substring(location.origin.length),
        }),
    );
};

const httpUpdateHandler = async () => {
    startUpdate();
    const body = JSON.stringify({
        state_token: stateToken,
        events: popInputEvents(),
    });

    const response: AppHttpPostResponse = await fetch(location.href, {
        method: "POST",
        body: body,
        headers: {
            "Content-Type": "application/json",
        },
        credentials: "include",
    }).then((res) => res.json());

    for (const part of response.html_parts) {
        applyHTML(part);
    }
    stateToken = response.state_token;
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

(window as any).rxxxt = {
    navigate: (url: string | URL) => {
        handleOutputEvents([
            { event: "navigate", location: new URL(url, location.href).href },
        ]);
        update();
    },
    init: (data: InitData) => {
        baseUrl = new URL(location.href);
        if (baseUrl.pathname.endsWith(data.path)) {
            baseUrl.pathname = baseUrl.pathname.slice(
                0,
                baseUrl.pathname.length - data.path.length,
            );
        } else {
            console.warn("Invalid base url!");
        }

        window.addEventListener("popstate", update);
        stateToken = data.state_token;
        handleOutputEvents(data.events);
        applyHTML();
    },
};
