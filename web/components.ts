const virtualElementStyle = "contents";
const queryAttributeNames = ["name", "query", "selector", "pattern"] as const;

abstract class BaseEventElement extends HTMLElement {
    protected listener: EventListener = (event: Event) => this.dispatchEvent(event);
    protected attributeValues = new Map<string, string | null>();

    public static get observedAttributes(): string[] {
        return [];
    }

    private get allPresent() {
        return (this.constructor as typeof BaseEventElement).observedAttributes.every((a) => this.attributeValues.has(a));
    }

    connectedCallback() {
        this.style.display = virtualElementStyle;
        if (this.allPresent) {
            this.doRegister();
        }
    }

    attributeChangedCallback(name: string, oldValue: string | null, newValue: string | null) {
        if (this.allPresent) {
            this.doUnregister();
            this.attributeValues.set(name, newValue);
            this.doRegister();
        }
    }

    disconnectedCallback() {
        if (this.allPresent) {
            this.doUnregister();
        }
    }

    protected abstract doRegister(): void;
    protected abstract doUnregister(): void;
}

class WindowEventElement extends BaseEventElement {
    static get observedAttributes() {
        return ["name"];
    }

    protected doRegister() {
        window.addEventListener(this.attributeValues.get("name")!, this.listener);
    }

    protected doUnregister() {
        window.removeEventListener(this.attributeValues.get("name")!, this.listener);
    }
}

class QuerySelectorEventElement extends BaseEventElement {
    static get observedAttributes() {
        return ["name", "selector"];
    }

    private registeredElements?: NodeListOf<Element>;

    protected doRegister() {
        this.registeredElements = document.querySelectorAll(this.attributeValues.get("selector")!);
        this.registeredElements.forEach(e => {
            e.addEventListener(this.attributeValues.get("name")!, this.listener);
        });
    }

    protected doUnregister() {
        if (this.registeredElements != undefined) {
            this.registeredElements.forEach(e => {
                e.removeEventListener(this.attributeValues.get("name")!, this.listener);
            });
        }
    }
}

customElements.define("rxxxt-window-event", WindowEventElement);
customElements.define("rxxxt-query-selector-event", QuerySelectorEventElement);
