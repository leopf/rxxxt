import morphdom from "morphdom";
import objectPath from "object-path";

interface SetCookieOutputEvent {
    event: "set-cookie"
}

interface ForceRefreshOutputEvent {
    event: "force-refresh"
}

interface NavigateOutputEvent {
    event: "navigate",
    location: string
}

type OutputEvent = SetCookieOutputEvent | ForceRefreshOutputEvent | NavigateOutputEvent;

interface ContextInputEvent {
    context_id: string;
    handler_name: string;
    data: Record<string, number | string | boolean>;
}

interface ContextInputEventDescription {
    context_id: string;
    handler_name: string;
    param_map: Record<string, string>,
    options: {}
}

interface AppHttpPostResponse {
    stateToken: string,
    events: OutputEvent[]
    html: string
}

interface InitData {
    stateToken: string,
    events: OutputEvent[]
}

let root: HTMLElement;
let stateToken: string = "";
let refreshScheduled: boolean = false;
const inputEvents: ContextInputEvent[] = [];
const trackedElements = new WeakMap<Node, string[]>();
const eventPrefix = "razz-on-";

const eventHandler = (e: Event) => {
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
        const eventField = eventDesc[outField];
        eventData[outField] = objectPath.get(e, eventField);
    }
    
    inputEvents.push({
        context_id: eventDesc.context_id,
        data: eventData,
        handler_name: eventDesc.handler_name
    });

    refreshPage();
};

const runRefreshPage = async () => {
    const body = JSON.stringify({
        stateToken,
        events: inputEvents
    });
    inputEvents.length = 0;

    const result: AppHttpPostResponse = await fetch(location.href, {
        method: "POST",
        body: body,
        headers: {
            "Content-Type": "application/json"
        },
        credentials: "include",
    }).then(res => res.json());

    const temp = document.createElement("div");
    temp.innerHTML = result.html;
    morphdom(root, temp, { childrenOnly: true });
    applyEventHandlers();

    stateToken = result.stateToken;
    handleOutputEvents(result.events);
};

const refreshPage = () => {
    if (!refreshScheduled) {
        refreshScheduled = true;
        setTimeout(() => {
            refreshScheduled = false;   
            runRefreshPage();
        }, 0);
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
        // TODO: more events
    }

    if (refresh) {
        refreshPage();
    }
};

const applyEventHandlers = () => {
    for (const element of root.getElementsByTagName("*")) {
        const appliedEvents = new Set(trackedElements.get(element) ?? []);
        const pendingEvents = new Set<string>();

        for (const attributeName of element.getAttributeNames()) {
            if (attributeName.startsWith(eventPrefix)) {
                const eventName = attributeName.substring(eventPrefix.length);
                pendingEvents.add(eventName);
            }
        }

        for (const eventName of appliedEvents) {
            if (!pendingEvents.has(eventName)) {
                element.removeEventListener(eventName, eventHandler);
            }
        }

        for (const eventName of pendingEvents) {
            if (!appliedEvents.has(eventName)) {
                console.log("adding listener to", element, eventName)
                element.addEventListener(eventName, eventHandler);
            }
        }

        trackedElements.set(element, Array.from(pendingEvents));
    }
};

(window as any).razzInit = (data: InitData) => {
    root = document.getElementById("razz-root")!;
    stateToken = data.stateToken;
    handleOutputEvents(data.events);
    applyEventHandlers();
};