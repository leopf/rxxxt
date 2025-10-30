import Chart from "https://cdn.jsdelivr.net/npm/chart.js@4/auto/+esm";

const css = `
:host {
    display: flex;
    overflow: hidden;
    align-items: center;
    justify-content: center;
}
`;

class ChartJsElement extends HTMLElement {
    static observedAttributes = ["config"];

    constructor() {
        super();
        this.attachShadow({ mode: "open" });
        const style = document.createElement("style");
        style.textContent = css;
        this._canvas = document.createElement("canvas");
        this.shadowRoot.append(style, this._canvas);

        this._chart = undefined;
        this._config = undefined;
    }

    connectedCallback() {
        this.#render();
    }
    disconnectedCallback() {
        this.#destroy();
    }
    attributeChangedCallback(name, oldVal, newVal) {
        if (name === "config" && oldVal !== newVal) {
            this._config = JSON.parse(newVal);
            this._config.options = this._config.options || {};
            if (this._config.options.responsive === undefined) {
                this._config.options.responsive = true;
            }
            this.#render();
        }
    }

    #destroy() {
        if (this._chart) {
            this._chart.destroy();
            this._chart = undefined;
        }
    }

    #render() {
        this.#destroy();
        this._chart = new Chart(this._canvas.getContext("2d"), this._config);
    }
}

customElements.define("chart-js", ChartJsElement);
