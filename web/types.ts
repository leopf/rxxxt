export type PrimitveRecord = Record<string, number | string | boolean | undefined>;

export type CustomEventHandler = (data: PrimitveRecord) => any;

export type OutputEvent =
    | CustomOutputEvent
    | SetCookieOutputEvent
    | NavigateOutputEvent
    | UseWebsocketOutputEvent;

export interface CustomOutputEvent {
    event: "custom";
    name: string;
    data: PrimitveRecord;
}

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
    requires_refresh?: boolean;
}

export interface UseWebsocketOutputEvent {
    event: "use-websocket";
    websocket: boolean;
}

export interface InputEvent {
    context_id: string;
    data: PrimitveRecord;
}

export interface InputEventDescriptor {
    context_id: string;
    options: {
        throttle?: number;
        debounce?: number;
        no_trigger?: boolean;
        prevent_default?: boolean;
        param_map: Record<string, string>;
        default_params?: PrimitveRecord;
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
    enable_web_socket_state_updates?: boolean;
    disable_http_update_retry?: boolean;
    events: OutputEvent[];
    path: string;
}
