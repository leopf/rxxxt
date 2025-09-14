import { initEventManager } from "./events";
import { initTransport, TransportConfig } from "./transport";
import { InitData, OutputEvent } from "./types";
import morphdom from "morphdom";

const defaultTargetId = "root";
let baseUrl: URL | undefined;

const transportConfig: TransportConfig = {
    stateToken: "",
    enableWebSocketStateUpdates: false,
    onUpdate: (htmlParts: string[], events: OutputEvent[]) => {
        for (const htmlPart of htmlParts) {
            applyHTML(htmlPart);
        }
        onOutputEvents(events);
    },
    popPendingEvents: () => eventManager.popPendingEvents()
};

const transport = initTransport(transportConfig);
const eventManager = initEventManager(transport.update);

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
        morphdom(target, updateRoot, {
            onNodeDiscarded: node => {
                if (node instanceof Element) {
                    eventManager.onElementDeleted(node);
                }
            }
        });
    }

    for (const element of target.getElementsByTagName("*")) {
        eventManager.onElementUpdated(element);
    }
};

const outputEventHandlers: { [K in OutputEvent['event']]: (ev: Extract<OutputEvent, { event: K }>) => void; } = {
    navigate: event => {
        const targetUrl = new URL(event.location, location.href);
        if (baseUrl === undefined || baseUrl.origin !== targetUrl.origin || !targetUrl.pathname.startsWith(baseUrl.pathname)) {
            location.assign(targetUrl);
        } else {
            window.history.pushState({}, "", event.location);
        }
    },
    "use-websocket": event => {
        if (event.websocket) {
            transport.useWebSocket();
        } else {
            transport.useHTTP();
        }
    },
    "set-cookie": event => {
        const parts: string[] = [`${event.name}=${event.value ?? ""}`];
        if (typeof event.path === "string") parts.push(`path=${event.path}`);
        if (typeof event.expires === "string") parts.push(`expires=${new Date(event.expires).toUTCString()}`);
        if (typeof event.max_age === "number") parts.push(`max-age=${event.max_age}`);
        if (typeof event.domain === "string") parts.push(`domain=${event.domain}`);
        if (event.secure) parts.push(`secure`);
        if (event.http_only) parts.push(`httponly`);

        document.cookie = parts.join(";");
    },
    "event-modify-window": event => {
        if (event.mode === "add") {
            eventManager.registerEvent(window, event.name, event.descriptor);
        } else if (event.mode === "remove") {
            eventManager.unregisterEvent(window, event.name, event.descriptor);
        }
    },
    "event-modify-query-selector": event => {
        let elements: EventTarget[];
        if (event.all) {
            elements = Array.from(document.querySelectorAll(event.selector));
        } else {
            const element = document.querySelector(event.selector);
            elements = element === null ? [] : [element];
        }
        for (const element of elements) {
            if (event.mode === "add") {
                eventManager.registerEvent(element, event.name, event.descriptor);
            } else if (event.mode === "remove") {
                eventManager.unregisterEvent(element, event.name, event.descriptor);
            }
        }
    }
};

const onOutputEvents = (events: OutputEvent[]) => events.forEach(event => outputEventHandlers[event.event](event as any)); // typescript doesnt handle this well

(window as any).rxxxt = {
    navigate: (url: string | URL) => {
        onOutputEvents([{ event: "navigate", location: new URL(url, location.href).href }]);
        transport.update();
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

        window.addEventListener("popstate", transport.update);
        transportConfig.stateToken = data.state_token;
        onOutputEvents(data.events);
        applyHTML();
    },
};
