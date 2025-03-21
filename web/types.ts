export type OutputEvent =
    | SetCookieOutputEvent
    | NavigateOutputEvent
    | UseWebsocketOutputEvent
    | EventRegisterWindowEvent
    | EventRegisterQuerySelectorEvent;
export type InputEventProducer = () => ContextInputEvent[];

export interface SetCookieOutputEvent {
    event: "set-cookie";
    name: string;
    value?: string;
    expires?: string;
    path?: string;
    max_age?: number;
    secure?: boolean;
    http_only?: boolean;
    domain?: string;
}

export interface NavigateOutputEvent {
    event: "navigate";
    location: string;
}

export interface UseWebsocketOutputEvent {
    event: "use-websocket";
    websocket: boolean;
}

export interface EventRegisterWindowEvent {
    event: "event-register-window";
    name: string;
    descriptor: ContextInputEventDescriptor;
}

export interface EventRegisterQuerySelectorEvent {
    event: "event-register-query-selector";
    name: string;
    selector: string;
    all: boolean;
    descriptor: ContextInputEventDescriptor;
}

export interface ContextInputEvent {
    context_id: string;
    data: Record<string, number | string | boolean>;
}

export interface ContextInputEventDescriptor {
    context_id: string;
    handler_name: string;
    param_map: Record<string, string>;
    options: {
        throttle?: number;
        debounce?: number;
        prevent_default?: boolean;
    };
}

export interface AppHttpPostResponse {
    state_token: string;
    events: OutputEvent[];
    html_parts: string[];
}

export interface AppWebsocketResponse {
    state_token?: string;
    events: OutputEvent[];
    html_parts: string[];
}

export interface InitData {
    state_token: string;
    events: OutputEvent[];
    path: string;
}

export interface ContextCleanable {
    clean: (ids: Set<string>) => void;
}
