import { AppHttpPostResponse, AppWebsocketResponse, ContextInputEvent, OutputEvent } from "./types";

export type TransportConfig = {
    popPendingEvents: () => Map<number, ContextInputEvent>;
    peekPendingEventIds: () => number[];
    onUpdate: (htmlParts: string[], events: OutputEvent[]) => void;
    enableWebSocketStateUpdates: boolean;
    stateToken: string;
};

export function initTransport(config: TransportConfig) {
    let ws: WebSocket | undefined = undefined;
    let isUpdateRunning = false;
    let isUpdatePending = false;
    let isUpdateScheduling = false;
    let updateHandler: ((events: ContextInputEvent[]) => Promise<void>);
    const pendingEvents = new Map<number, ContextInputEvent>();

    const update = () => {
        if (isUpdateRunning) {
            isUpdatePending = true;
            return;
        }
        isUpdateRunning = true;
        isUpdatePending = false;

        for (const item of config.popPendingEvents()) {
            pendingEvents.set(item[0], item[1]);
        }
        updateHandler(Array.from(pendingEvents.values()));
    };
    const finishUpdate = (htmlParts: string[], events: OutputEvent[]) => {
        if (config.peekPendingEventIds().some(eventId => pendingEvents.has(eventId))) {
            isUpdatePending = true;
        }
        else {
            pendingEvents.clear();
            config.onUpdate(htmlParts, events);
        }

        isUpdateRunning = false;
        if (isUpdatePending) {
            update();
        }
    };

    const useHTTP = () => {
        ws?.close();
        ws = undefined;
        updateHandler = async (events: ContextInputEvent[]) => {
            const httpResponse = await fetch(location.href, {
                method: "POST",
                body: JSON.stringify({ state_token: config.stateToken, events }),
                headers: { "Content-Type": "application/json" },
                credentials: "include"
            });
            if (httpResponse.ok) {
                const response: AppHttpPostResponse = await httpResponse.json();
                finishUpdate(response.html_parts, response.events);
                config.stateToken = response.state_token ?? config.stateToken;
            }
            else {
                // TODO: implement retry for some error codes
                throw new Error(`Update failed! Server responded with ${httpResponse.statusText} (${httpResponse.status}).`);
            }
        };
    };
    const useWebSocket = () => {
        if (ws !== undefined) {
            console.warn("tried to switch to websocket again, despite using it already");
            return;
        }

        const wsUpdateHandler: typeof updateHandler = async (events: ContextInputEvent[]) =>
            ws?.send(
                JSON.stringify({
                    type: "update",
                    events: events,
                    location: location.href.substring(location.origin.length),
                }),
            );

        const url = new URL(location.href);
        url.protocol = location.protocol == "https:" ? "wss" : "ws";
        ws = new WebSocket(url);
        ws.addEventListener("close", useHTTP); // TODO handle close with pending update
        ws.addEventListener("open", () => {
            updateHandler = wsUpdateHandler;
            ws?.send(
                JSON.stringify({ type: "init", state_token: config.stateToken, enable_state_updates: config.enableWebSocketStateUpdates }));
        });
        ws.addEventListener("message", (e) => {
            if (typeof e.data !== "string") return;
            const response: AppWebsocketResponse = JSON.parse(e.data);
            config.stateToken = response.state_token ?? config.stateToken;
            finishUpdate(response.html_parts, response.events);
        });
    };

    useHTTP();

    return {
        useHTTP, useWebSocket,
        update: () => {
            if (isUpdateScheduling) return;
            isUpdateScheduling = true;
            setTimeout(() => {
                isUpdateScheduling = false;
                update();
            }, 0);
        }
    };
}
