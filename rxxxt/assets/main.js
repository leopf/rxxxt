(() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropSymbols = Object.getOwnPropertySymbols;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __propIsEnum = Object.prototype.propertyIsEnumerable;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __spreadValues = (a, b) => {
    for (var prop in b || (b = {}))
      if (__hasOwnProp.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    if (__getOwnPropSymbols)
      for (var prop of __getOwnPropSymbols(b)) {
        if (__propIsEnum.call(b, prop))
          __defNormalProp(a, prop, b[prop]);
      }
    return a;
  };
  var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);

  // web/components.ts
  var virtualElementStyle = "contents";
  var BaseEventElement = class extends HTMLElement {
    constructor() {
      super(...arguments);
      __publicField(this, "listener", (event) => this.dispatchEvent(new CustomEvent("emit", { detail: event })));
      __publicField(this, "attributeValues", /* @__PURE__ */ new Map());
    }
    static get observedAttributes() {
      return [];
    }
    get allPresent() {
      return this.constructor.observedAttributes.every((a) => this.attributeValues.has(a));
    }
    connectedCallback() {
      this.style.display = virtualElementStyle;
      if (this.allPresent) {
        this.doRegister();
      }
    }
    attributeChangedCallback(name, oldValue, newValue) {
      if (this.allPresent) {
        this.doUnregister();
      }
      this.attributeValues.set(name, newValue);
      if (this.allPresent) {
        this.doRegister();
      }
    }
    disconnectedCallback() {
      if (this.allPresent) {
        this.doUnregister();
      }
    }
  };
  var WindowEventElement = class extends BaseEventElement {
    static get observedAttributes() {
      return ["name"];
    }
    doRegister() {
      window.addEventListener(this.attributeValues.get("name"), this.listener);
    }
    doUnregister() {
      window.removeEventListener(this.attributeValues.get("name"), this.listener);
    }
  };
  var QuerySelectorEventElement = class extends BaseEventElement {
    constructor() {
      super(...arguments);
      __publicField(this, "registeredElements");
    }
    static get observedAttributes() {
      return ["name", "selector"];
    }
    doRegister() {
      this.registeredElements = document.querySelectorAll(this.attributeValues.get("selector"));
      this.registeredElements.forEach((e) => {
        e.addEventListener(this.attributeValues.get("name"), this.listener);
      });
    }
    doUnregister() {
      if (this.registeredElements != void 0) {
        this.registeredElements.forEach((e) => {
          e.removeEventListener(this.attributeValues.get("name"), this.listener);
        });
      }
    }
  };
  customElements.define("rxxxt-window-event", WindowEventElement);
  customElements.define("rxxxt-query-selector-event", QuerySelectorEventElement);

  // web/events.ts
  var eventPrefix = "rxxxt-on-";
  var now = () => (/* @__PURE__ */ new Date()).getTime();
  var _RegisteredEvent = class _RegisteredEvent {
    constructor(triggerCallback, submitMap, descriptorRaw) {
      __publicField(this, "descriptorRaw");
      __publicField(this, "handler");
      __publicField(this, "submitId");
      __publicField(this, "triggerCallback");
      __publicField(this, "submitMap");
      __publicField(this, "timeoutHandle");
      __publicField(this, "lastCall");
      this.triggerCallback = triggerCallback;
      this.descriptorRaw = descriptorRaw;
      this.handler = this.handle.bind(this);
      this.submitMap = submitMap;
      this.submitId = ++_RegisteredEvent.submitIdCounter;
    }
    get descriptor() {
      return JSON.parse(atob(this.descriptorRaw));
    }
    handle(e) {
      var _a, _b, _c, _d, _e;
      const eventData = __spreadValues(__spreadValues({}, (_a = this.descriptor.options.default_params) != null ? _a : {}), Object.fromEntries(Object.entries((_b = this.descriptor.options.param_map) != null ? _b : {}).map((entry) => [entry[0], getEventPathValue(e, entry[1])])));
      this.submitMap.set(this.submitId, {
        context_id: this.descriptor.context_id,
        data: eventData
      });
      if (this.timeoutHandle) {
        clearTimeout(this.timeoutHandle);
        this.timeoutHandle = void 0;
      }
      if (this.descriptor.options.prevent_default) {
        e.preventDefault();
      }
      if (!this.descriptor.options.no_trigger) {
        const waitTime = Math.max(
          0,
          (_c = this.descriptor.options.debounce) != null ? _c : 0,
          ((_d = this.lastCall) != null ? _d : 0) + ((_e = this.descriptor.options.throttle) != null ? _e : 0) - now()
        );
        this.timeoutHandle = setTimeout(() => {
          if (this.submitMap.has(this.submitId)) {
            this.lastCall = now();
            this.triggerCallback();
          }
        }, waitTime);
      }
    }
  };
  __publicField(_RegisteredEvent, "submitIdCounter", 0);
  var RegisteredEvent = _RegisteredEvent;
  function getLocalElementEventDescriptors(element) {
    const res = /* @__PURE__ */ new Map();
    for (const attributeName of element.getAttributeNames()) {
      if (attributeName.startsWith(eventPrefix)) {
        const eventName = attributeName.substring(eventPrefix.length);
        const rawDescriptor = element.getAttribute(attributeName);
        if (rawDescriptor !== null) {
          res.set(eventName, rawDescriptor);
        }
      }
    }
    return res;
  }
  function getEventPathValue(event, path) {
    let value = event;
    try {
      for (const part of path.split(".")) {
        value = value[part];
      }
      if (typeof value == "string" || typeof value == "number" || typeof value == "boolean") {
        return value;
      } else {
        return void 0;
      }
    } catch (e) {
      return void 0;
    }
  }
  function initEventManager(triggerUpdate) {
    const targetRegisteredEvents = /* @__PURE__ */ new WeakMap();
    const submitMap = /* @__PURE__ */ new Map();
    const popPendingEvents = () => {
      const result = new Map(submitMap);
      submitMap.clear();
      return result;
    };
    const onElementUpdated = (element) => {
      var _a;
      const newEventDescriptors = getLocalElementEventDescriptors(element);
      const registeredEvents = (_a = targetRegisteredEvents.get(element)) != null ? _a : /* @__PURE__ */ new Map();
      targetRegisteredEvents.set(element, registeredEvents);
      for (const registeredEventName of registeredEvents == null ? void 0 : registeredEvents.keys()) {
        if (!newEventDescriptors.has(registeredEventName)) {
          element.removeEventListener(registeredEventName, registeredEvents.get(registeredEventName).handler);
          registeredEvents.delete(registeredEventName);
        }
      }
      for (const item of newEventDescriptors.entries()) {
        const registeredEvent = registeredEvents.get(item[0]);
        if (registeredEvent === void 0) {
          const newRegisteredEvent = new RegisteredEvent(triggerUpdate, submitMap, item[1]);
          element.addEventListener(item[0], newRegisteredEvent.handler);
          registeredEvents.set(item[0], newRegisteredEvent);
        } else {
          registeredEvent.descriptorRaw = item[1];
        }
      }
    };
    return { onElementUpdated, popPendingEvents };
  }

  // web/transport.ts
  function initTransport(config) {
    let ws = void 0;
    let isUpdateRunning = false;
    let isUpdatePending = false;
    let isUpdateScheduling = false;
    let updateHandler;
    const pendingEvents = /* @__PURE__ */ new Map();
    const movePendingEvents = () => {
      const foundEvents = config.popPendingEvents();
      for (const item of foundEvents) {
        pendingEvents.set(item[0], item[1]);
      }
      return foundEvents.size;
    };
    const update = () => {
      if (isUpdateRunning) {
        isUpdatePending = true;
        return;
      }
      isUpdateRunning = true;
      isUpdatePending = false;
      movePendingEvents();
      updateHandler(Array.from(pendingEvents.values()));
    };
    const finishUpdate = (htmlParts, events) => {
      pendingEvents.clear();
      config.onUpdate(htmlParts, events);
      isUpdateRunning = false;
      if (isUpdatePending) {
        update();
      }
    };
    const useHTTP = () => {
      ws == null ? void 0 : ws.close();
      ws = void 0;
      updateHandler = async (events) => {
        var _a;
        const httpResponse = await fetch(location.href, {
          method: "POST",
          body: JSON.stringify({ state_token: config.stateToken, events }),
          headers: { "Content-Type": "application/json" },
          credentials: "include"
        });
        if (httpResponse.ok) {
          const response = await httpResponse.json();
          if (movePendingEvents() > 0 && !config.disableHTTPRetry) {
            console.info("retry http update");
            isUpdateRunning = false;
            update();
          } else {
            finishUpdate(response.html_parts, response.events);
            config.stateToken = (_a = response.state_token) != null ? _a : config.stateToken;
          }
        } else {
          finishUpdate([], []);
          throw new Error("Update failed! Server responded with ".concat(httpResponse.statusText, " (").concat(httpResponse.status, ")."));
        }
      };
    };
    const useWebSocket = () => {
      if (ws !== void 0) {
        console.warn("tried to switch to websocket again, despite using it already");
        return;
      }
      const wsUpdateHandler = async (events) => ws == null ? void 0 : ws.send(
        JSON.stringify({
          type: "update",
          events,
          location: location.href.substring(location.origin.length)
        })
      );
      const url = new URL(location.href);
      url.protocol = location.protocol == "https:" ? "wss" : "ws";
      ws = new WebSocket(url);
      ws.addEventListener("close", useHTTP);
      ws.addEventListener("open", () => {
        var _a;
        updateHandler = wsUpdateHandler;
        ws == null ? void 0 : ws.send(
          JSON.stringify({ type: "init", state_token: config.stateToken, enable_state_updates: (_a = config.enableWebSocketStateUpdates) != null ? _a : false })
        );
      });
      ws.addEventListener("message", (e) => {
        var _a;
        if (typeof e.data !== "string") return;
        const response = JSON.parse(e.data);
        config.stateToken = (_a = response.state_token) != null ? _a : config.stateToken;
        finishUpdate(response.html_parts, response.events);
      });
    };
    useHTTP();
    return {
      useHTTP,
      useWebSocket,
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

  // node_modules/.pnpm/morphdom@2.7.4/node_modules/morphdom/dist/morphdom-esm.js
  var DOCUMENT_FRAGMENT_NODE = 11;
  function morphAttrs(fromNode, toNode) {
    var toNodeAttrs = toNode.attributes;
    var attr;
    var attrName;
    var attrNamespaceURI;
    var attrValue;
    var fromValue;
    if (toNode.nodeType === DOCUMENT_FRAGMENT_NODE || fromNode.nodeType === DOCUMENT_FRAGMENT_NODE) {
      return;
    }
    for (var i = toNodeAttrs.length - 1; i >= 0; i--) {
      attr = toNodeAttrs[i];
      attrName = attr.name;
      attrNamespaceURI = attr.namespaceURI;
      attrValue = attr.value;
      if (attrNamespaceURI) {
        attrName = attr.localName || attrName;
        fromValue = fromNode.getAttributeNS(attrNamespaceURI, attrName);
        if (fromValue !== attrValue) {
          if (attr.prefix === "xmlns") {
            attrName = attr.name;
          }
          fromNode.setAttributeNS(attrNamespaceURI, attrName, attrValue);
        }
      } else {
        fromValue = fromNode.getAttribute(attrName);
        if (fromValue !== attrValue) {
          fromNode.setAttribute(attrName, attrValue);
        }
      }
    }
    var fromNodeAttrs = fromNode.attributes;
    for (var d = fromNodeAttrs.length - 1; d >= 0; d--) {
      attr = fromNodeAttrs[d];
      attrName = attr.name;
      attrNamespaceURI = attr.namespaceURI;
      if (attrNamespaceURI) {
        attrName = attr.localName || attrName;
        if (!toNode.hasAttributeNS(attrNamespaceURI, attrName)) {
          fromNode.removeAttributeNS(attrNamespaceURI, attrName);
        }
      } else {
        if (!toNode.hasAttribute(attrName)) {
          fromNode.removeAttribute(attrName);
        }
      }
    }
  }
  var range;
  var NS_XHTML = "http://www.w3.org/1999/xhtml";
  var doc = typeof document === "undefined" ? void 0 : document;
  var HAS_TEMPLATE_SUPPORT = !!doc && "content" in doc.createElement("template");
  var HAS_RANGE_SUPPORT = !!doc && doc.createRange && "createContextualFragment" in doc.createRange();
  function createFragmentFromTemplate(str) {
    var template = doc.createElement("template");
    template.innerHTML = str;
    return template.content.childNodes[0];
  }
  function createFragmentFromRange(str) {
    if (!range) {
      range = doc.createRange();
      range.selectNode(doc.body);
    }
    var fragment = range.createContextualFragment(str);
    return fragment.childNodes[0];
  }
  function createFragmentFromWrap(str) {
    var fragment = doc.createElement("body");
    fragment.innerHTML = str;
    return fragment.childNodes[0];
  }
  function toElement(str) {
    str = str.trim();
    if (HAS_TEMPLATE_SUPPORT) {
      return createFragmentFromTemplate(str);
    } else if (HAS_RANGE_SUPPORT) {
      return createFragmentFromRange(str);
    }
    return createFragmentFromWrap(str);
  }
  function compareNodeNames(fromEl, toEl) {
    var fromNodeName = fromEl.nodeName;
    var toNodeName = toEl.nodeName;
    var fromCodeStart, toCodeStart;
    if (fromNodeName === toNodeName) {
      return true;
    }
    fromCodeStart = fromNodeName.charCodeAt(0);
    toCodeStart = toNodeName.charCodeAt(0);
    if (fromCodeStart <= 90 && toCodeStart >= 97) {
      return fromNodeName === toNodeName.toUpperCase();
    } else if (toCodeStart <= 90 && fromCodeStart >= 97) {
      return toNodeName === fromNodeName.toUpperCase();
    } else {
      return false;
    }
  }
  function createElementNS(name, namespaceURI) {
    return !namespaceURI || namespaceURI === NS_XHTML ? doc.createElement(name) : doc.createElementNS(namespaceURI, name);
  }
  function moveChildren(fromEl, toEl) {
    var curChild = fromEl.firstChild;
    while (curChild) {
      var nextChild = curChild.nextSibling;
      toEl.appendChild(curChild);
      curChild = nextChild;
    }
    return toEl;
  }
  function syncBooleanAttrProp(fromEl, toEl, name) {
    if (fromEl[name] !== toEl[name]) {
      fromEl[name] = toEl[name];
      if (fromEl[name]) {
        fromEl.setAttribute(name, "");
      } else {
        fromEl.removeAttribute(name);
      }
    }
  }
  var specialElHandlers = {
    OPTION: function(fromEl, toEl) {
      var parentNode = fromEl.parentNode;
      if (parentNode) {
        var parentName = parentNode.nodeName.toUpperCase();
        if (parentName === "OPTGROUP") {
          parentNode = parentNode.parentNode;
          parentName = parentNode && parentNode.nodeName.toUpperCase();
        }
        if (parentName === "SELECT" && !parentNode.hasAttribute("multiple")) {
          if (fromEl.hasAttribute("selected") && !toEl.selected) {
            fromEl.setAttribute("selected", "selected");
            fromEl.removeAttribute("selected");
          }
          parentNode.selectedIndex = -1;
        }
      }
      syncBooleanAttrProp(fromEl, toEl, "selected");
    },
    /**
     * The "value" attribute is special for the <input> element since it sets
     * the initial value. Changing the "value" attribute without changing the
     * "value" property will have no effect since it is only used to the set the
     * initial value.  Similar for the "checked" attribute, and "disabled".
     */
    INPUT: function(fromEl, toEl) {
      syncBooleanAttrProp(fromEl, toEl, "checked");
      syncBooleanAttrProp(fromEl, toEl, "disabled");
      if (fromEl.value !== toEl.value) {
        fromEl.value = toEl.value;
      }
      if (!toEl.hasAttribute("value")) {
        fromEl.removeAttribute("value");
      }
    },
    TEXTAREA: function(fromEl, toEl) {
      var newValue = toEl.value;
      if (fromEl.value !== newValue) {
        fromEl.value = newValue;
      }
      var firstChild = fromEl.firstChild;
      if (firstChild) {
        var oldValue = firstChild.nodeValue;
        if (oldValue == newValue || !newValue && oldValue == fromEl.placeholder) {
          return;
        }
        firstChild.nodeValue = newValue;
      }
    },
    SELECT: function(fromEl, toEl) {
      if (!toEl.hasAttribute("multiple")) {
        var selectedIndex = -1;
        var i = 0;
        var curChild = fromEl.firstChild;
        var optgroup;
        var nodeName;
        while (curChild) {
          nodeName = curChild.nodeName && curChild.nodeName.toUpperCase();
          if (nodeName === "OPTGROUP") {
            optgroup = curChild;
            curChild = optgroup.firstChild;
          } else {
            if (nodeName === "OPTION") {
              if (curChild.hasAttribute("selected")) {
                selectedIndex = i;
                break;
              }
              i++;
            }
            curChild = curChild.nextSibling;
            if (!curChild && optgroup) {
              curChild = optgroup.nextSibling;
              optgroup = null;
            }
          }
        }
        fromEl.selectedIndex = selectedIndex;
      }
    }
  };
  var ELEMENT_NODE = 1;
  var DOCUMENT_FRAGMENT_NODE$1 = 11;
  var TEXT_NODE = 3;
  var COMMENT_NODE = 8;
  function noop() {
  }
  function defaultGetNodeKey(node) {
    if (node) {
      return node.getAttribute && node.getAttribute("id") || node.id;
    }
  }
  function morphdomFactory(morphAttrs2) {
    return function morphdom2(fromNode, toNode, options) {
      if (!options) {
        options = {};
      }
      if (typeof toNode === "string") {
        if (fromNode.nodeName === "#document" || fromNode.nodeName === "HTML" || fromNode.nodeName === "BODY") {
          var toNodeHtml = toNode;
          toNode = doc.createElement("html");
          toNode.innerHTML = toNodeHtml;
        } else {
          toNode = toElement(toNode);
        }
      } else if (toNode.nodeType === DOCUMENT_FRAGMENT_NODE$1) {
        toNode = toNode.firstElementChild;
      }
      var getNodeKey = options.getNodeKey || defaultGetNodeKey;
      var onBeforeNodeAdded = options.onBeforeNodeAdded || noop;
      var onNodeAdded = options.onNodeAdded || noop;
      var onBeforeElUpdated = options.onBeforeElUpdated || noop;
      var onElUpdated = options.onElUpdated || noop;
      var onBeforeNodeDiscarded = options.onBeforeNodeDiscarded || noop;
      var onNodeDiscarded = options.onNodeDiscarded || noop;
      var onBeforeElChildrenUpdated = options.onBeforeElChildrenUpdated || noop;
      var skipFromChildren = options.skipFromChildren || noop;
      var addChild = options.addChild || function(parent, child) {
        return parent.appendChild(child);
      };
      var childrenOnly = options.childrenOnly === true;
      var fromNodesLookup = /* @__PURE__ */ Object.create(null);
      var keyedRemovalList = [];
      function addKeyedRemoval(key) {
        keyedRemovalList.push(key);
      }
      function walkDiscardedChildNodes(node, skipKeyedNodes) {
        if (node.nodeType === ELEMENT_NODE) {
          var curChild = node.firstChild;
          while (curChild) {
            var key = void 0;
            if (skipKeyedNodes && (key = getNodeKey(curChild))) {
              addKeyedRemoval(key);
            } else {
              onNodeDiscarded(curChild);
              if (curChild.firstChild) {
                walkDiscardedChildNodes(curChild, skipKeyedNodes);
              }
            }
            curChild = curChild.nextSibling;
          }
        }
      }
      function removeNode(node, parentNode, skipKeyedNodes) {
        if (onBeforeNodeDiscarded(node) === false) {
          return;
        }
        if (parentNode) {
          parentNode.removeChild(node);
        }
        onNodeDiscarded(node);
        walkDiscardedChildNodes(node, skipKeyedNodes);
      }
      function indexTree(node) {
        if (node.nodeType === ELEMENT_NODE || node.nodeType === DOCUMENT_FRAGMENT_NODE$1) {
          var curChild = node.firstChild;
          while (curChild) {
            var key = getNodeKey(curChild);
            if (key) {
              fromNodesLookup[key] = curChild;
            }
            indexTree(curChild);
            curChild = curChild.nextSibling;
          }
        }
      }
      indexTree(fromNode);
      function handleNodeAdded(el) {
        onNodeAdded(el);
        var curChild = el.firstChild;
        while (curChild) {
          var nextSibling = curChild.nextSibling;
          var key = getNodeKey(curChild);
          if (key) {
            var unmatchedFromEl = fromNodesLookup[key];
            if (unmatchedFromEl && compareNodeNames(curChild, unmatchedFromEl)) {
              curChild.parentNode.replaceChild(unmatchedFromEl, curChild);
              morphEl(unmatchedFromEl, curChild);
            } else {
              handleNodeAdded(curChild);
            }
          } else {
            handleNodeAdded(curChild);
          }
          curChild = nextSibling;
        }
      }
      function cleanupFromEl(fromEl, curFromNodeChild, curFromNodeKey) {
        while (curFromNodeChild) {
          var fromNextSibling = curFromNodeChild.nextSibling;
          if (curFromNodeKey = getNodeKey(curFromNodeChild)) {
            addKeyedRemoval(curFromNodeKey);
          } else {
            removeNode(
              curFromNodeChild,
              fromEl,
              true
              /* skip keyed nodes */
            );
          }
          curFromNodeChild = fromNextSibling;
        }
      }
      function morphEl(fromEl, toEl, childrenOnly2) {
        var toElKey = getNodeKey(toEl);
        if (toElKey) {
          delete fromNodesLookup[toElKey];
        }
        if (!childrenOnly2) {
          var beforeUpdateResult = onBeforeElUpdated(fromEl, toEl);
          if (beforeUpdateResult === false) {
            return;
          } else if (beforeUpdateResult instanceof HTMLElement) {
            fromEl = beforeUpdateResult;
            indexTree(fromEl);
          }
          morphAttrs2(fromEl, toEl);
          onElUpdated(fromEl);
          if (onBeforeElChildrenUpdated(fromEl, toEl) === false) {
            return;
          }
        }
        if (fromEl.nodeName !== "TEXTAREA") {
          morphChildren(fromEl, toEl);
        } else {
          specialElHandlers.TEXTAREA(fromEl, toEl);
        }
      }
      function morphChildren(fromEl, toEl) {
        var skipFrom = skipFromChildren(fromEl, toEl);
        var curToNodeChild = toEl.firstChild;
        var curFromNodeChild = fromEl.firstChild;
        var curToNodeKey;
        var curFromNodeKey;
        var fromNextSibling;
        var toNextSibling;
        var matchingFromEl;
        outer: while (curToNodeChild) {
          toNextSibling = curToNodeChild.nextSibling;
          curToNodeKey = getNodeKey(curToNodeChild);
          while (!skipFrom && curFromNodeChild) {
            fromNextSibling = curFromNodeChild.nextSibling;
            if (curToNodeChild.isSameNode && curToNodeChild.isSameNode(curFromNodeChild)) {
              curToNodeChild = toNextSibling;
              curFromNodeChild = fromNextSibling;
              continue outer;
            }
            curFromNodeKey = getNodeKey(curFromNodeChild);
            var curFromNodeType = curFromNodeChild.nodeType;
            var isCompatible = void 0;
            if (curFromNodeType === curToNodeChild.nodeType) {
              if (curFromNodeType === ELEMENT_NODE) {
                if (curToNodeKey) {
                  if (curToNodeKey !== curFromNodeKey) {
                    if (matchingFromEl = fromNodesLookup[curToNodeKey]) {
                      if (fromNextSibling === matchingFromEl) {
                        isCompatible = false;
                      } else {
                        fromEl.insertBefore(matchingFromEl, curFromNodeChild);
                        if (curFromNodeKey) {
                          addKeyedRemoval(curFromNodeKey);
                        } else {
                          removeNode(
                            curFromNodeChild,
                            fromEl,
                            true
                            /* skip keyed nodes */
                          );
                        }
                        curFromNodeChild = matchingFromEl;
                        curFromNodeKey = getNodeKey(curFromNodeChild);
                      }
                    } else {
                      isCompatible = false;
                    }
                  }
                } else if (curFromNodeKey) {
                  isCompatible = false;
                }
                isCompatible = isCompatible !== false && compareNodeNames(curFromNodeChild, curToNodeChild);
                if (isCompatible) {
                  morphEl(curFromNodeChild, curToNodeChild);
                }
              } else if (curFromNodeType === TEXT_NODE || curFromNodeType == COMMENT_NODE) {
                isCompatible = true;
                if (curFromNodeChild.nodeValue !== curToNodeChild.nodeValue) {
                  curFromNodeChild.nodeValue = curToNodeChild.nodeValue;
                }
              }
            }
            if (isCompatible) {
              curToNodeChild = toNextSibling;
              curFromNodeChild = fromNextSibling;
              continue outer;
            }
            if (curFromNodeKey) {
              addKeyedRemoval(curFromNodeKey);
            } else {
              removeNode(
                curFromNodeChild,
                fromEl,
                true
                /* skip keyed nodes */
              );
            }
            curFromNodeChild = fromNextSibling;
          }
          if (curToNodeKey && (matchingFromEl = fromNodesLookup[curToNodeKey]) && compareNodeNames(matchingFromEl, curToNodeChild)) {
            if (!skipFrom) {
              addChild(fromEl, matchingFromEl);
            }
            morphEl(matchingFromEl, curToNodeChild);
          } else {
            var onBeforeNodeAddedResult = onBeforeNodeAdded(curToNodeChild);
            if (onBeforeNodeAddedResult !== false) {
              if (onBeforeNodeAddedResult) {
                curToNodeChild = onBeforeNodeAddedResult;
              }
              if (curToNodeChild.actualize) {
                curToNodeChild = curToNodeChild.actualize(fromEl.ownerDocument || doc);
              }
              addChild(fromEl, curToNodeChild);
              handleNodeAdded(curToNodeChild);
            }
          }
          curToNodeChild = toNextSibling;
          curFromNodeChild = fromNextSibling;
        }
        cleanupFromEl(fromEl, curFromNodeChild, curFromNodeKey);
        var specialElHandler = specialElHandlers[fromEl.nodeName];
        if (specialElHandler) {
          specialElHandler(fromEl, toEl);
        }
      }
      var morphedNode = fromNode;
      var morphedNodeType = morphedNode.nodeType;
      var toNodeType = toNode.nodeType;
      if (!childrenOnly) {
        if (morphedNodeType === ELEMENT_NODE) {
          if (toNodeType === ELEMENT_NODE) {
            if (!compareNodeNames(fromNode, toNode)) {
              onNodeDiscarded(fromNode);
              morphedNode = moveChildren(fromNode, createElementNS(toNode.nodeName, toNode.namespaceURI));
            }
          } else {
            morphedNode = toNode;
          }
        } else if (morphedNodeType === TEXT_NODE || morphedNodeType === COMMENT_NODE) {
          if (toNodeType === morphedNodeType) {
            if (morphedNode.nodeValue !== toNode.nodeValue) {
              morphedNode.nodeValue = toNode.nodeValue;
            }
            return morphedNode;
          } else {
            morphedNode = toNode;
          }
        }
      }
      if (morphedNode === toNode) {
        onNodeDiscarded(fromNode);
      } else {
        if (toNode.isSameNode && toNode.isSameNode(morphedNode)) {
          return;
        }
        morphEl(morphedNode, toNode, childrenOnly);
        if (keyedRemovalList) {
          for (var i = 0, len = keyedRemovalList.length; i < len; i++) {
            var elToRemove = fromNodesLookup[keyedRemovalList[i]];
            if (elToRemove) {
              removeNode(elToRemove, elToRemove.parentNode, false);
            }
          }
        }
      }
      if (!childrenOnly && morphedNode !== fromNode && fromNode.parentNode) {
        if (morphedNode.actualize) {
          morphedNode = morphedNode.actualize(fromNode.ownerDocument || doc);
        }
        fromNode.parentNode.replaceChild(morphedNode, fromNode);
      }
      return morphedNode;
    };
  }
  var morphdom = morphdomFactory(morphAttrs);
  var morphdom_esm_default = morphdom;

  // web/index.ts
  var defaultTargetId = "root";
  var outputCustomEventHandlers = /* @__PURE__ */ new Map();
  var originUrl;
  var transportConfig = {
    stateToken: "",
    onUpdate: (htmlParts, events) => {
      for (const htmlPart of htmlParts) {
        applyHTML(htmlPart);
      }
      onOutputEvents(events);
    },
    popPendingEvents: () => eventManager.popPendingEvents()
  };
  var transport = initTransport(transportConfig);
  var eventManager = initEventManager(transport.update);
  var applyHTML = (html) => {
    let target;
    if (html === void 0) {
      const ttarget = document.getElementById(defaultTargetId);
      if (ttarget === null) {
        throw new Error("Update target not found!");
      }
      target = ttarget;
    } else {
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
      morphdom_esm_default(target, updateRoot);
    }
    for (const element of target.getElementsByTagName("*")) {
      eventManager.onElementUpdated(element);
    }
  };
  var outputEventHandlers = {
    custom: (event) => {
      var _a;
      for (const handler of (_a = outputCustomEventHandlers.get(event.name)) != null ? _a : []) {
        try {
          handler(event.data);
        } catch (e) {
          console.error(e);
        }
      }
    },
    navigate: (event) => {
      const targetUrl = new URL(event.location, location.href);
      if (originUrl === void 0 || originUrl !== targetUrl.origin) {
        location.assign(targetUrl);
      } else {
        window.history.pushState({}, "", event.location);
        if (event.requires_refresh) {
          transport.update();
        }
      }
    },
    "use-websocket": (event) => {
      if (event.websocket) {
        transport.useWebSocket();
      } else {
        transport.useHTTP();
      }
    },
    "set-cookie": (event) => {
      var _a;
      const parts = ["".concat(event.name, "=").concat((_a = event.value) != null ? _a : "")];
      if (typeof event.path === "string") parts.push("path=".concat(event.path));
      if (typeof event.expires === "string") parts.push("expires=".concat(new Date(event.expires).toUTCString()));
      if (typeof event.max_age === "number") parts.push("max-age=".concat(event.max_age));
      if (typeof event.domain === "string") parts.push("domain=".concat(event.domain));
      if (event.secure) parts.push("secure");
      if (event.http_only) parts.push("httponly");
      document.cookie = parts.join(";");
    }
  };
  var onOutputEvents = (events) => events.forEach((event) => outputEventHandlers[event.event](event));
  var rxxxt = {
    on: (name, handler) => {
      var _a;
      const handlers = (_a = outputCustomEventHandlers.get(name)) != null ? _a : /* @__PURE__ */ new Set();
      outputCustomEventHandlers.set(name, handlers);
      handlers.add(handler);
    },
    off: (name, handler) => {
      var _a;
      const handlers = (_a = outputCustomEventHandlers.get(name)) != null ? _a : /* @__PURE__ */ new Set();
      return handlers.delete(handler);
    },
    navigate: (url) => {
      onOutputEvents([{ event: "navigate", location: new URL(url, location.href).href, requires_refresh: true }]);
    },
    init: (data) => {
      originUrl = new URL(location.href).origin;
      window.addEventListener("popstate", transport.update);
      transportConfig.stateToken = data.state_token;
      transportConfig.enableWebSocketStateUpdates = data.enable_web_socket_state_updates;
      transportConfig.disableHTTPRetry = data.disable_http_update_retry;
      onOutputEvents(data.events);
      applyHTML();
    }
  };
  window.rxxxt = rxxxt;
  var initDataElement = document.getElementById("rxxxt-init-data");
  if (initDataElement != null && initDataElement.textContent !== null) {
    rxxxt.init(JSON.parse(initDataElement.textContent));
  } else {
    console.warn("failed to initialize rxxxt. init data not found.");
  }
})();
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiLi4vLi4vd2ViL2NvbXBvbmVudHMudHMiLCAiLi4vLi4vd2ViL2V2ZW50cy50cyIsICIuLi8uLi93ZWIvdHJhbnNwb3J0LnRzIiwgIi4uLy4uL25vZGVfbW9kdWxlcy8ucG5wbS9tb3JwaGRvbUAyLjcuNC9ub2RlX21vZHVsZXMvbW9ycGhkb20vZGlzdC9tb3JwaGRvbS1lc20uanMiLCAiLi4vLi4vd2ViL2luZGV4LnRzIl0sCiAgInNvdXJjZXNDb250ZW50IjogWyJjb25zdCB2aXJ0dWFsRWxlbWVudFN0eWxlID0gXCJjb250ZW50c1wiO1xuY29uc3QgcXVlcnlBdHRyaWJ1dGVOYW1lcyA9IFtcIm5hbWVcIiwgXCJxdWVyeVwiLCBcInNlbGVjdG9yXCIsIFwicGF0dGVyblwiXSBhcyBjb25zdDtcblxuYWJzdHJhY3QgY2xhc3MgQmFzZUV2ZW50RWxlbWVudCBleHRlbmRzIEhUTUxFbGVtZW50IHtcbiAgICBwcm90ZWN0ZWQgbGlzdGVuZXI6IEV2ZW50TGlzdGVuZXIgPSAoZXZlbnQ6IEV2ZW50KSA9PiB0aGlzLmRpc3BhdGNoRXZlbnQobmV3IEN1c3RvbUV2ZW50KFwiZW1pdFwiLCB7IGRldGFpbDogZXZlbnQgfSkpO1xuICAgIHByb3RlY3RlZCBhdHRyaWJ1dGVWYWx1ZXMgPSBuZXcgTWFwPHN0cmluZywgc3RyaW5nIHwgbnVsbD4oKTtcblxuICAgIHB1YmxpYyBzdGF0aWMgZ2V0IG9ic2VydmVkQXR0cmlidXRlcygpOiBzdHJpbmdbXSB7XG4gICAgICAgIHJldHVybiBbXTtcbiAgICB9XG5cbiAgICBwcml2YXRlIGdldCBhbGxQcmVzZW50KCkge1xuICAgICAgICByZXR1cm4gKHRoaXMuY29uc3RydWN0b3IgYXMgdHlwZW9mIEJhc2VFdmVudEVsZW1lbnQpLm9ic2VydmVkQXR0cmlidXRlcy5ldmVyeSgoYSkgPT4gdGhpcy5hdHRyaWJ1dGVWYWx1ZXMuaGFzKGEpKTtcbiAgICB9XG5cbiAgICBjb25uZWN0ZWRDYWxsYmFjaygpIHtcbiAgICAgICAgdGhpcy5zdHlsZS5kaXNwbGF5ID0gdmlydHVhbEVsZW1lbnRTdHlsZTtcbiAgICAgICAgaWYgKHRoaXMuYWxsUHJlc2VudCkge1xuICAgICAgICAgICAgdGhpcy5kb1JlZ2lzdGVyKCk7XG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBhdHRyaWJ1dGVDaGFuZ2VkQ2FsbGJhY2sobmFtZTogc3RyaW5nLCBvbGRWYWx1ZTogc3RyaW5nIHwgbnVsbCwgbmV3VmFsdWU6IHN0cmluZyB8IG51bGwpIHtcbiAgICAgICAgaWYgKHRoaXMuYWxsUHJlc2VudCkge1xuICAgICAgICAgICAgdGhpcy5kb1VucmVnaXN0ZXIoKTtcbiAgICAgICAgfVxuICAgICAgICB0aGlzLmF0dHJpYnV0ZVZhbHVlcy5zZXQobmFtZSwgbmV3VmFsdWUpO1xuICAgICAgICBpZiAodGhpcy5hbGxQcmVzZW50KSB7XG4gICAgICAgICAgICB0aGlzLmRvUmVnaXN0ZXIoKTtcbiAgICAgICAgfVxuICAgIH1cblxuICAgIGRpc2Nvbm5lY3RlZENhbGxiYWNrKCkge1xuICAgICAgICBpZiAodGhpcy5hbGxQcmVzZW50KSB7XG4gICAgICAgICAgICB0aGlzLmRvVW5yZWdpc3RlcigpO1xuICAgICAgICB9XG4gICAgfVxuXG4gICAgcHJvdGVjdGVkIGFic3RyYWN0IGRvUmVnaXN0ZXIoKTogdm9pZDtcbiAgICBwcm90ZWN0ZWQgYWJzdHJhY3QgZG9VbnJlZ2lzdGVyKCk6IHZvaWQ7XG59XG5cbmNsYXNzIFdpbmRvd0V2ZW50RWxlbWVudCBleHRlbmRzIEJhc2VFdmVudEVsZW1lbnQge1xuICAgIHN0YXRpYyBnZXQgb2JzZXJ2ZWRBdHRyaWJ1dGVzKCkge1xuICAgICAgICByZXR1cm4gW1wibmFtZVwiXTtcbiAgICB9XG5cbiAgICBwcm90ZWN0ZWQgZG9SZWdpc3RlcigpIHtcbiAgICAgICAgd2luZG93LmFkZEV2ZW50TGlzdGVuZXIodGhpcy5hdHRyaWJ1dGVWYWx1ZXMuZ2V0KFwibmFtZVwiKSEsIHRoaXMubGlzdGVuZXIpO1xuICAgIH1cblxuICAgIHByb3RlY3RlZCBkb1VucmVnaXN0ZXIoKSB7XG4gICAgICAgIHdpbmRvdy5yZW1vdmVFdmVudExpc3RlbmVyKHRoaXMuYXR0cmlidXRlVmFsdWVzLmdldChcIm5hbWVcIikhLCB0aGlzLmxpc3RlbmVyKTtcbiAgICB9XG59XG5cbmNsYXNzIFF1ZXJ5U2VsZWN0b3JFdmVudEVsZW1lbnQgZXh0ZW5kcyBCYXNlRXZlbnRFbGVtZW50IHtcbiAgICBzdGF0aWMgZ2V0IG9ic2VydmVkQXR0cmlidXRlcygpIHtcbiAgICAgICAgcmV0dXJuIFtcIm5hbWVcIiwgXCJzZWxlY3RvclwiXTtcbiAgICB9XG5cbiAgICBwcml2YXRlIHJlZ2lzdGVyZWRFbGVtZW50cz86IE5vZGVMaXN0T2Y8RWxlbWVudD47XG5cbiAgICBwcm90ZWN0ZWQgZG9SZWdpc3RlcigpIHtcbiAgICAgICAgdGhpcy5yZWdpc3RlcmVkRWxlbWVudHMgPSBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKHRoaXMuYXR0cmlidXRlVmFsdWVzLmdldChcInNlbGVjdG9yXCIpISk7XG4gICAgICAgIHRoaXMucmVnaXN0ZXJlZEVsZW1lbnRzLmZvckVhY2goZSA9PiB7XG4gICAgICAgICAgICBlLmFkZEV2ZW50TGlzdGVuZXIodGhpcy5hdHRyaWJ1dGVWYWx1ZXMuZ2V0KFwibmFtZVwiKSEsIHRoaXMubGlzdGVuZXIpO1xuICAgICAgICB9KTtcbiAgICB9XG5cbiAgICBwcm90ZWN0ZWQgZG9VbnJlZ2lzdGVyKCkge1xuICAgICAgICBpZiAodGhpcy5yZWdpc3RlcmVkRWxlbWVudHMgIT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICB0aGlzLnJlZ2lzdGVyZWRFbGVtZW50cy5mb3JFYWNoKGUgPT4ge1xuICAgICAgICAgICAgICAgIGUucmVtb3ZlRXZlbnRMaXN0ZW5lcih0aGlzLmF0dHJpYnV0ZVZhbHVlcy5nZXQoXCJuYW1lXCIpISwgdGhpcy5saXN0ZW5lcik7XG4gICAgICAgICAgICB9KTtcbiAgICAgICAgfVxuICAgIH1cbn1cblxuY3VzdG9tRWxlbWVudHMuZGVmaW5lKFwicnh4eHQtd2luZG93LWV2ZW50XCIsIFdpbmRvd0V2ZW50RWxlbWVudCk7XG5jdXN0b21FbGVtZW50cy5kZWZpbmUoXCJyeHh4dC1xdWVyeS1zZWxlY3Rvci1ldmVudFwiLCBRdWVyeVNlbGVjdG9yRXZlbnRFbGVtZW50KTtcbiIsICJpbXBvcnQgeyBJbnB1dEV2ZW50LCBJbnB1dEV2ZW50RGVzY3JpcHRvciB9IGZyb20gXCIuL3R5cGVzXCI7XG5cbmNvbnN0IGV2ZW50UHJlZml4ID0gXCJyeHh4dC1vbi1cIjtcbmNvbnN0IG5vdyA9ICgpID0+IG5ldyBEYXRlKCkuZ2V0VGltZSgpO1xuXG5jbGFzcyBSZWdpc3RlcmVkRXZlbnQge1xuICAgIHByaXZhdGUgc3RhdGljIHN1Ym1pdElkQ291bnRlciA9IDA7XG5cbiAgICBwdWJsaWMgZGVzY3JpcHRvclJhdzogc3RyaW5nO1xuICAgIHB1YmxpYyBoYW5kbGVyOiAoZTogRXZlbnQpID0+IHZvaWQ7XG5cbiAgICBwcml2YXRlIHJlYWRvbmx5IHN1Ym1pdElkOiBudW1iZXI7XG4gICAgcHJpdmF0ZSByZWFkb25seSB0cmlnZ2VyQ2FsbGJhY2s6ICgpID0+IHZvaWQ7XG4gICAgcHJpdmF0ZSByZWFkb25seSBzdWJtaXRNYXA6IE1hcDxudW1iZXIsIElucHV0RXZlbnQ+O1xuXG4gICAgcHJpdmF0ZSBnZXQgZGVzY3JpcHRvcigpIHtcbiAgICAgICAgcmV0dXJuIEpTT04ucGFyc2UoYXRvYih0aGlzLmRlc2NyaXB0b3JSYXcpKSBhcyBJbnB1dEV2ZW50RGVzY3JpcHRvcjtcbiAgICB9XG5cbiAgICBwcml2YXRlIHRpbWVvdXRIYW5kbGU/OiBudW1iZXI7XG4gICAgcHJpdmF0ZSBsYXN0Q2FsbD86IG51bWJlcjtcblxuICAgIGNvbnN0cnVjdG9yKHRyaWdnZXJDYWxsYmFjazogKCkgPT4gdm9pZCwgc3VibWl0TWFwOiBNYXA8bnVtYmVyLCBJbnB1dEV2ZW50PiwgZGVzY3JpcHRvclJhdzogc3RyaW5nKSB7XG4gICAgICAgIHRoaXMudHJpZ2dlckNhbGxiYWNrID0gdHJpZ2dlckNhbGxiYWNrO1xuICAgICAgICB0aGlzLmRlc2NyaXB0b3JSYXcgPSBkZXNjcmlwdG9yUmF3O1xuICAgICAgICB0aGlzLmhhbmRsZXIgPSB0aGlzLmhhbmRsZS5iaW5kKHRoaXMpO1xuICAgICAgICB0aGlzLnN1Ym1pdE1hcCA9IHN1Ym1pdE1hcDtcbiAgICAgICAgdGhpcy5zdWJtaXRJZCA9ICsrUmVnaXN0ZXJlZEV2ZW50LnN1Ym1pdElkQ291bnRlcjtcbiAgICB9XG5cbiAgICBwcml2YXRlIGhhbmRsZShlOiBFdmVudCkge1xuICAgICAgICBjb25zdCBldmVudERhdGE6IFJlY29yZDxzdHJpbmcsIG51bWJlciB8IGJvb2xlYW4gfCBzdHJpbmcgfCB1bmRlZmluZWQ+ID0ge1xuICAgICAgICAgICAgLi4uKHRoaXMuZGVzY3JpcHRvci5vcHRpb25zLmRlZmF1bHRfcGFyYW1zID8/IHt9KSxcbiAgICAgICAgICAgIC4uLk9iamVjdC5mcm9tRW50cmllcyhPYmplY3QuZW50cmllcyh0aGlzLmRlc2NyaXB0b3Iub3B0aW9ucy5wYXJhbV9tYXAgPz8ge30pXG4gICAgICAgICAgICAgICAgLm1hcChlbnRyeSA9PiBbZW50cnlbMF0sIGdldEV2ZW50UGF0aFZhbHVlKGUsIGVudHJ5WzFdKV0pKVxuICAgICAgICB9O1xuXG4gICAgICAgIHRoaXMuc3VibWl0TWFwLnNldCh0aGlzLnN1Ym1pdElkLCB7XG4gICAgICAgICAgICBjb250ZXh0X2lkOiB0aGlzLmRlc2NyaXB0b3IuY29udGV4dF9pZCxcbiAgICAgICAgICAgIGRhdGE6IGV2ZW50RGF0YVxuICAgICAgICB9KTtcblxuICAgICAgICBpZiAodGhpcy50aW1lb3V0SGFuZGxlKSB7XG4gICAgICAgICAgICBjbGVhclRpbWVvdXQodGhpcy50aW1lb3V0SGFuZGxlKTtcbiAgICAgICAgICAgIHRoaXMudGltZW91dEhhbmRsZSA9IHVuZGVmaW5lZDtcbiAgICAgICAgfVxuXG4gICAgICAgIGlmICh0aGlzLmRlc2NyaXB0b3Iub3B0aW9ucy5wcmV2ZW50X2RlZmF1bHQpIHtcbiAgICAgICAgICAgIGUucHJldmVudERlZmF1bHQoKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGlmICghdGhpcy5kZXNjcmlwdG9yLm9wdGlvbnMubm9fdHJpZ2dlcikge1xuICAgICAgICAgICAgY29uc3Qgd2FpdFRpbWUgPSBNYXRoLm1heChcbiAgICAgICAgICAgICAgICAwLFxuICAgICAgICAgICAgICAgIHRoaXMuZGVzY3JpcHRvci5vcHRpb25zLmRlYm91bmNlID8/IDAsXG4gICAgICAgICAgICAgICAgKHRoaXMubGFzdENhbGwgPz8gMCkgKyAodGhpcy5kZXNjcmlwdG9yLm9wdGlvbnMudGhyb3R0bGUgPz8gMCkgLSBub3coKVxuICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgdGhpcy50aW1lb3V0SGFuZGxlID0gc2V0VGltZW91dCgoKSA9PiB7XG4gICAgICAgICAgICAgICAgaWYgKHRoaXMuc3VibWl0TWFwLmhhcyh0aGlzLnN1Ym1pdElkKSkge1xuICAgICAgICAgICAgICAgICAgICB0aGlzLmxhc3RDYWxsID0gbm93KCk7XG4gICAgICAgICAgICAgICAgICAgIHRoaXMudHJpZ2dlckNhbGxiYWNrKCk7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSwgd2FpdFRpbWUpO1xuICAgICAgICB9XG4gICAgfVxufVxuXG5mdW5jdGlvbiBnZXRMb2NhbEVsZW1lbnRFdmVudERlc2NyaXB0b3JzKGVsZW1lbnQ6IEVsZW1lbnQpICB7XG4gICAgY29uc3QgcmVzID0gbmV3IE1hcDxzdHJpbmcsIHN0cmluZz4oKTtcblxuICAgIGZvciAoY29uc3QgYXR0cmlidXRlTmFtZSBvZiBlbGVtZW50LmdldEF0dHJpYnV0ZU5hbWVzKCkpIHtcbiAgICAgICAgaWYgKGF0dHJpYnV0ZU5hbWUuc3RhcnRzV2l0aChldmVudFByZWZpeCkpIHtcbiAgICAgICAgICAgIGNvbnN0IGV2ZW50TmFtZSA9IGF0dHJpYnV0ZU5hbWUuc3Vic3RyaW5nKGV2ZW50UHJlZml4Lmxlbmd0aCk7XG4gICAgICAgICAgICBjb25zdCByYXdEZXNjcmlwdG9yID0gZWxlbWVudC5nZXRBdHRyaWJ1dGUoYXR0cmlidXRlTmFtZSk7XG4gICAgICAgICAgICBpZiAocmF3RGVzY3JpcHRvciAhPT0gbnVsbCkge1xuICAgICAgICAgICAgICAgIHJlcy5zZXQoZXZlbnROYW1lLCByYXdEZXNjcmlwdG9yKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiByZXM7XG59XG5cbmZ1bmN0aW9uIGdldEV2ZW50UGF0aFZhbHVlKGV2ZW50OiBFdmVudCwgcGF0aDogc3RyaW5nKSB7XG4gICAgbGV0IHZhbHVlID0gZXZlbnQgYXMgYW55OyAvLyBhbnkgbmVlZGVkIGZvciB0eXBpbmcuLi5cbiAgICB0cnkge1xuICAgICAgICBmb3IgKGNvbnN0IHBhcnQgb2YgcGF0aC5zcGxpdChcIi5cIikpIHtcbiAgICAgICAgICAgIHZhbHVlID0gdmFsdWVbcGFydF07XG4gICAgICAgIH1cbiAgICAgICAgaWYgKHR5cGVvZiB2YWx1ZSA9PSBcInN0cmluZ1wiIHx8IHR5cGVvZiB2YWx1ZSA9PSBcIm51bWJlclwiIHx8IHR5cGVvZiB2YWx1ZSA9PSBcImJvb2xlYW5cIikge1xuICAgICAgICAgICAgcmV0dXJuIHZhbHVlO1xuICAgICAgICB9XG4gICAgICAgIGVsc2Uge1xuICAgICAgICAgICAgcmV0dXJuIHVuZGVmaW5lZDtcbiAgICAgICAgfVxuICAgIH1cbiAgICBjYXRjaCB7XG4gICAgICAgIHJldHVybiB1bmRlZmluZWQ7XG4gICAgfVxufVxuXG5leHBvcnQgZnVuY3Rpb24gaW5pdEV2ZW50TWFuYWdlcih0cmlnZ2VyVXBkYXRlOiAoKSA9PiB2b2lkKSB7XG4gICAgY29uc3QgdGFyZ2V0UmVnaXN0ZXJlZEV2ZW50cyA9IG5ldyBXZWFrTWFwPEV2ZW50VGFyZ2V0LCBNYXA8c3RyaW5nLCBSZWdpc3RlcmVkRXZlbnQ+PigpO1xuICAgIGNvbnN0IHN1Ym1pdE1hcCA9IG5ldyBNYXA8bnVtYmVyLCBJbnB1dEV2ZW50PigpO1xuXG4gICAgY29uc3QgcG9wUGVuZGluZ0V2ZW50cyA9ICgpID0+IHtcbiAgICAgICAgY29uc3QgcmVzdWx0ID0gbmV3IE1hcChzdWJtaXRNYXApO1xuICAgICAgICBzdWJtaXRNYXAuY2xlYXIoKTtcbiAgICAgICAgcmV0dXJuIHJlc3VsdDtcbiAgICB9O1xuICAgIGNvbnN0IG9uRWxlbWVudFVwZGF0ZWQgPSAoZWxlbWVudDogRWxlbWVudCkgPT4ge1xuICAgICAgICBjb25zdCBuZXdFdmVudERlc2NyaXB0b3JzID0gZ2V0TG9jYWxFbGVtZW50RXZlbnREZXNjcmlwdG9ycyhlbGVtZW50KTtcbiAgICAgICAgY29uc3QgcmVnaXN0ZXJlZEV2ZW50cyA9IHRhcmdldFJlZ2lzdGVyZWRFdmVudHMuZ2V0KGVsZW1lbnQpID8/IG5ldyBNYXA8c3RyaW5nLCBSZWdpc3RlcmVkRXZlbnQ+KCk7XG4gICAgICAgIHRhcmdldFJlZ2lzdGVyZWRFdmVudHMuc2V0KGVsZW1lbnQsIHJlZ2lzdGVyZWRFdmVudHMpO1xuXG4gICAgICAgIGZvciAoY29uc3QgcmVnaXN0ZXJlZEV2ZW50TmFtZSBvZiByZWdpc3RlcmVkRXZlbnRzPy5rZXlzKCkpIHtcbiAgICAgICAgICAgIGlmICghbmV3RXZlbnREZXNjcmlwdG9ycy5oYXMocmVnaXN0ZXJlZEV2ZW50TmFtZSkpIHtcbiAgICAgICAgICAgICAgICBlbGVtZW50LnJlbW92ZUV2ZW50TGlzdGVuZXIocmVnaXN0ZXJlZEV2ZW50TmFtZSwgcmVnaXN0ZXJlZEV2ZW50cy5nZXQocmVnaXN0ZXJlZEV2ZW50TmFtZSkhLmhhbmRsZXIpO1xuICAgICAgICAgICAgICAgIHJlZ2lzdGVyZWRFdmVudHMuZGVsZXRlKHJlZ2lzdGVyZWRFdmVudE5hbWUpO1xuICAgICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgZm9yIChjb25zdCBpdGVtIG9mIG5ld0V2ZW50RGVzY3JpcHRvcnMuZW50cmllcygpKSB7XG4gICAgICAgICAgICBjb25zdCByZWdpc3RlcmVkRXZlbnQgPSByZWdpc3RlcmVkRXZlbnRzLmdldChpdGVtWzBdKTtcbiAgICAgICAgICAgIGlmIChyZWdpc3RlcmVkRXZlbnQgPT09IHVuZGVmaW5lZCkge1xuICAgICAgICAgICAgICAgIGNvbnN0IG5ld1JlZ2lzdGVyZWRFdmVudCA9IG5ldyBSZWdpc3RlcmVkRXZlbnQodHJpZ2dlclVwZGF0ZSwgc3VibWl0TWFwLCBpdGVtWzFdKTtcbiAgICAgICAgICAgICAgICBlbGVtZW50LmFkZEV2ZW50TGlzdGVuZXIoaXRlbVswXSwgbmV3UmVnaXN0ZXJlZEV2ZW50LmhhbmRsZXIpO1xuICAgICAgICAgICAgICAgIHJlZ2lzdGVyZWRFdmVudHMuc2V0KGl0ZW1bMF0sIG5ld1JlZ2lzdGVyZWRFdmVudCk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBlbHNlIHtcbiAgICAgICAgICAgICAgICByZWdpc3RlcmVkRXZlbnQuZGVzY3JpcHRvclJhdyA9IGl0ZW1bMV07XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICB9O1xuXG4gICAgcmV0dXJuIHsgb25FbGVtZW50VXBkYXRlZCwgcG9wUGVuZGluZ0V2ZW50cyB9O1xufVxuIiwgImltcG9ydCB7IEFwcEh0dHBQb3N0UmVzcG9uc2UsIEFwcFdlYnNvY2tldFJlc3BvbnNlLCBJbnB1dEV2ZW50LCBPdXRwdXRFdmVudCB9IGZyb20gXCIuL3R5cGVzXCI7XG5cbmV4cG9ydCB0eXBlIFRyYW5zcG9ydENvbmZpZyA9IHtcbiAgICBwb3BQZW5kaW5nRXZlbnRzOiAoKSA9PiBNYXA8bnVtYmVyLCBJbnB1dEV2ZW50PjtcbiAgICBvblVwZGF0ZTogKGh0bWxQYXJ0czogc3RyaW5nW10sIGV2ZW50czogT3V0cHV0RXZlbnRbXSkgPT4gdm9pZDtcbiAgICBlbmFibGVXZWJTb2NrZXRTdGF0ZVVwZGF0ZXM/OiBib29sZWFuO1xuICAgIGRpc2FibGVIVFRQUmV0cnk/OiBib29sZWFuO1xuICAgIHN0YXRlVG9rZW46IHN0cmluZztcbn07XG5cbmV4cG9ydCBmdW5jdGlvbiBpbml0VHJhbnNwb3J0KGNvbmZpZzogVHJhbnNwb3J0Q29uZmlnKSB7XG4gICAgbGV0IHdzOiBXZWJTb2NrZXQgfCB1bmRlZmluZWQgPSB1bmRlZmluZWQ7XG4gICAgbGV0IGlzVXBkYXRlUnVubmluZyA9IGZhbHNlO1xuICAgIGxldCBpc1VwZGF0ZVBlbmRpbmcgPSBmYWxzZTtcbiAgICBsZXQgaXNVcGRhdGVTY2hlZHVsaW5nID0gZmFsc2U7XG4gICAgbGV0IHVwZGF0ZUhhbmRsZXI6ICgoZXZlbnRzOiBJbnB1dEV2ZW50W10pID0+IFByb21pc2U8dm9pZD4pO1xuICAgIGNvbnN0IHBlbmRpbmdFdmVudHMgPSBuZXcgTWFwPG51bWJlciwgSW5wdXRFdmVudD4oKTtcblxuICAgIGNvbnN0IG1vdmVQZW5kaW5nRXZlbnRzID0gKCkgPT4ge1xuICAgICAgICBjb25zdCBmb3VuZEV2ZW50cyA9IGNvbmZpZy5wb3BQZW5kaW5nRXZlbnRzKCk7XG4gICAgICAgIGZvciAoY29uc3QgaXRlbSBvZiBmb3VuZEV2ZW50cykge1xuICAgICAgICAgICAgcGVuZGluZ0V2ZW50cy5zZXQoaXRlbVswXSwgaXRlbVsxXSk7XG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIGZvdW5kRXZlbnRzLnNpemVcbiAgICB9O1xuICAgIGNvbnN0IHVwZGF0ZSA9ICgpID0+IHtcbiAgICAgICAgaWYgKGlzVXBkYXRlUnVubmluZykge1xuICAgICAgICAgICAgaXNVcGRhdGVQZW5kaW5nID0gdHJ1ZTtcbiAgICAgICAgICAgIHJldHVybjtcbiAgICAgICAgfVxuICAgICAgICBpc1VwZGF0ZVJ1bm5pbmcgPSB0cnVlO1xuICAgICAgICBpc1VwZGF0ZVBlbmRpbmcgPSBmYWxzZTtcblxuICAgICAgICBtb3ZlUGVuZGluZ0V2ZW50cygpO1xuICAgICAgICB1cGRhdGVIYW5kbGVyKEFycmF5LmZyb20ocGVuZGluZ0V2ZW50cy52YWx1ZXMoKSkpO1xuICAgIH07XG4gICAgY29uc3QgZmluaXNoVXBkYXRlID0gKGh0bWxQYXJ0czogc3RyaW5nW10sIGV2ZW50czogT3V0cHV0RXZlbnRbXSkgPT4ge1xuICAgICAgICBwZW5kaW5nRXZlbnRzLmNsZWFyKCk7XG4gICAgICAgIGNvbmZpZy5vblVwZGF0ZShodG1sUGFydHMsIGV2ZW50cyk7XG5cbiAgICAgICAgaXNVcGRhdGVSdW5uaW5nID0gZmFsc2U7XG4gICAgICAgIGlmIChpc1VwZGF0ZVBlbmRpbmcpIHtcbiAgICAgICAgICAgIHVwZGF0ZSgpO1xuICAgICAgICB9XG4gICAgfTtcblxuICAgIGNvbnN0IHVzZUhUVFAgPSAoKSA9PiB7XG4gICAgICAgIHdzPy5jbG9zZSgpO1xuICAgICAgICB3cyA9IHVuZGVmaW5lZDtcbiAgICAgICAgdXBkYXRlSGFuZGxlciA9IGFzeW5jIChldmVudHM6IElucHV0RXZlbnRbXSkgPT4ge1xuICAgICAgICAgICAgY29uc3QgaHR0cFJlc3BvbnNlID0gYXdhaXQgZmV0Y2gobG9jYXRpb24uaHJlZiwge1xuICAgICAgICAgICAgICAgIG1ldGhvZDogXCJQT1NUXCIsXG4gICAgICAgICAgICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBzdGF0ZV90b2tlbjogY29uZmlnLnN0YXRlVG9rZW4sIGV2ZW50cyB9KSxcbiAgICAgICAgICAgICAgICBoZWFkZXJzOiB7IFwiQ29udGVudC1UeXBlXCI6IFwiYXBwbGljYXRpb24vanNvblwiIH0sXG4gICAgICAgICAgICAgICAgY3JlZGVudGlhbHM6IFwiaW5jbHVkZVwiXG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIGlmIChodHRwUmVzcG9uc2Uub2spIHtcbiAgICAgICAgICAgICAgICBjb25zdCByZXNwb25zZTogQXBwSHR0cFBvc3RSZXNwb25zZSA9IGF3YWl0IGh0dHBSZXNwb25zZS5qc29uKCk7XG4gICAgICAgICAgICAgICAgaWYgKG1vdmVQZW5kaW5nRXZlbnRzKCkgPiAwICYmICFjb25maWcuZGlzYWJsZUhUVFBSZXRyeSkgeyAvLyByZXRyeSwgd29ya3Mgb25seSBvbiBodHRwIGFzIGl0IGlzIChzZXJ2ZXIgc2lkZSkgc3RhdGVsZXNzXG4gICAgICAgICAgICAgICAgICAgIGNvbnNvbGUuaW5mbyhcInJldHJ5IGh0dHAgdXBkYXRlXCIpO1xuICAgICAgICAgICAgICAgICAgICBpc1VwZGF0ZVJ1bm5pbmcgPSBmYWxzZTtcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlKCk7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIGVsc2Uge1xuICAgICAgICAgICAgICAgICAgICBmaW5pc2hVcGRhdGUocmVzcG9uc2UuaHRtbF9wYXJ0cywgcmVzcG9uc2UuZXZlbnRzKTtcbiAgICAgICAgICAgICAgICAgICAgY29uZmlnLnN0YXRlVG9rZW4gPSByZXNwb25zZS5zdGF0ZV90b2tlbiA/PyBjb25maWcuc3RhdGVUb2tlbjtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBlbHNlIHtcbiAgICAgICAgICAgICAgICBmaW5pc2hVcGRhdGUoW10sIFtdKTtcbiAgICAgICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoYFVwZGF0ZSBmYWlsZWQhIFNlcnZlciByZXNwb25kZWQgd2l0aCAke2h0dHBSZXNwb25zZS5zdGF0dXNUZXh0fSAoJHtodHRwUmVzcG9uc2Uuc3RhdHVzfSkuYCk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH07XG4gICAgfTtcbiAgICBjb25zdCB1c2VXZWJTb2NrZXQgPSAoKSA9PiB7XG4gICAgICAgIGlmICh3cyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICBjb25zb2xlLndhcm4oXCJ0cmllZCB0byBzd2l0Y2ggdG8gd2Vic29ja2V0IGFnYWluLCBkZXNwaXRlIHVzaW5nIGl0IGFscmVhZHlcIik7XG4gICAgICAgICAgICByZXR1cm47XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCB3c1VwZGF0ZUhhbmRsZXI6IHR5cGVvZiB1cGRhdGVIYW5kbGVyID0gYXN5bmMgKGV2ZW50czogSW5wdXRFdmVudFtdKSA9PlxuICAgICAgICAgICAgd3M/LnNlbmQoXG4gICAgICAgICAgICAgICAgSlNPTi5zdHJpbmdpZnkoe1xuICAgICAgICAgICAgICAgICAgICB0eXBlOiBcInVwZGF0ZVwiLFxuICAgICAgICAgICAgICAgICAgICBldmVudHM6IGV2ZW50cyxcbiAgICAgICAgICAgICAgICAgICAgbG9jYXRpb246IGxvY2F0aW9uLmhyZWYuc3Vic3RyaW5nKGxvY2F0aW9uLm9yaWdpbi5sZW5ndGgpLFxuICAgICAgICAgICAgICAgIH0pLFxuICAgICAgICAgICAgKTtcblxuICAgICAgICBjb25zdCB1cmwgPSBuZXcgVVJMKGxvY2F0aW9uLmhyZWYpO1xuICAgICAgICB1cmwucHJvdG9jb2wgPSBsb2NhdGlvbi5wcm90b2NvbCA9PSBcImh0dHBzOlwiID8gXCJ3c3NcIiA6IFwid3NcIjtcbiAgICAgICAgd3MgPSBuZXcgV2ViU29ja2V0KHVybCk7XG4gICAgICAgIHdzLmFkZEV2ZW50TGlzdGVuZXIoXCJjbG9zZVwiLCB1c2VIVFRQKTsgLy8gVE9ETyBoYW5kbGUgY2xvc2Ugd2l0aCBwZW5kaW5nIHVwZGF0ZVxuICAgICAgICB3cy5hZGRFdmVudExpc3RlbmVyKFwib3BlblwiLCAoKSA9PiB7XG4gICAgICAgICAgICB1cGRhdGVIYW5kbGVyID0gd3NVcGRhdGVIYW5kbGVyO1xuICAgICAgICAgICAgd3M/LnNlbmQoXG4gICAgICAgICAgICAgICAgSlNPTi5zdHJpbmdpZnkoeyB0eXBlOiBcImluaXRcIiwgc3RhdGVfdG9rZW46IGNvbmZpZy5zdGF0ZVRva2VuLCBlbmFibGVfc3RhdGVfdXBkYXRlczogY29uZmlnLmVuYWJsZVdlYlNvY2tldFN0YXRlVXBkYXRlcyA/PyBmYWxzZSB9KSk7XG4gICAgICAgIH0pO1xuICAgICAgICB3cy5hZGRFdmVudExpc3RlbmVyKFwibWVzc2FnZVwiLCAoZSkgPT4ge1xuICAgICAgICAgICAgaWYgKHR5cGVvZiBlLmRhdGEgIT09IFwic3RyaW5nXCIpIHJldHVybjtcbiAgICAgICAgICAgIGNvbnN0IHJlc3BvbnNlOiBBcHBXZWJzb2NrZXRSZXNwb25zZSA9IEpTT04ucGFyc2UoZS5kYXRhKTtcbiAgICAgICAgICAgIGNvbmZpZy5zdGF0ZVRva2VuID0gcmVzcG9uc2Uuc3RhdGVfdG9rZW4gPz8gY29uZmlnLnN0YXRlVG9rZW47XG4gICAgICAgICAgICBmaW5pc2hVcGRhdGUocmVzcG9uc2UuaHRtbF9wYXJ0cywgcmVzcG9uc2UuZXZlbnRzKTtcbiAgICAgICAgfSk7XG4gICAgfTtcblxuICAgIHVzZUhUVFAoKTtcblxuICAgIHJldHVybiB7XG4gICAgICAgIHVzZUhUVFAsIHVzZVdlYlNvY2tldCxcbiAgICAgICAgdXBkYXRlOiAoKSA9PiB7XG4gICAgICAgICAgICBpZiAoaXNVcGRhdGVTY2hlZHVsaW5nKSByZXR1cm47XG4gICAgICAgICAgICBpc1VwZGF0ZVNjaGVkdWxpbmcgPSB0cnVlO1xuICAgICAgICAgICAgc2V0VGltZW91dCgoKSA9PiB7XG4gICAgICAgICAgICAgICAgaXNVcGRhdGVTY2hlZHVsaW5nID0gZmFsc2U7XG4gICAgICAgICAgICAgICAgdXBkYXRlKCk7XG4gICAgICAgICAgICB9LCAwKTtcbiAgICAgICAgfVxuICAgIH07XG59XG4iLCAidmFyIERPQ1VNRU5UX0ZSQUdNRU5UX05PREUgPSAxMTtcblxuZnVuY3Rpb24gbW9ycGhBdHRycyhmcm9tTm9kZSwgdG9Ob2RlKSB7XG4gICAgdmFyIHRvTm9kZUF0dHJzID0gdG9Ob2RlLmF0dHJpYnV0ZXM7XG4gICAgdmFyIGF0dHI7XG4gICAgdmFyIGF0dHJOYW1lO1xuICAgIHZhciBhdHRyTmFtZXNwYWNlVVJJO1xuICAgIHZhciBhdHRyVmFsdWU7XG4gICAgdmFyIGZyb21WYWx1ZTtcblxuICAgIC8vIGRvY3VtZW50LWZyYWdtZW50cyBkb250IGhhdmUgYXR0cmlidXRlcyBzbyBsZXRzIG5vdCBkbyBhbnl0aGluZ1xuICAgIGlmICh0b05vZGUubm9kZVR5cGUgPT09IERPQ1VNRU5UX0ZSQUdNRU5UX05PREUgfHwgZnJvbU5vZGUubm9kZVR5cGUgPT09IERPQ1VNRU5UX0ZSQUdNRU5UX05PREUpIHtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICAvLyB1cGRhdGUgYXR0cmlidXRlcyBvbiBvcmlnaW5hbCBET00gZWxlbWVudFxuICAgIGZvciAodmFyIGkgPSB0b05vZGVBdHRycy5sZW5ndGggLSAxOyBpID49IDA7IGktLSkge1xuICAgICAgICBhdHRyID0gdG9Ob2RlQXR0cnNbaV07XG4gICAgICAgIGF0dHJOYW1lID0gYXR0ci5uYW1lO1xuICAgICAgICBhdHRyTmFtZXNwYWNlVVJJID0gYXR0ci5uYW1lc3BhY2VVUkk7XG4gICAgICAgIGF0dHJWYWx1ZSA9IGF0dHIudmFsdWU7XG5cbiAgICAgICAgaWYgKGF0dHJOYW1lc3BhY2VVUkkpIHtcbiAgICAgICAgICAgIGF0dHJOYW1lID0gYXR0ci5sb2NhbE5hbWUgfHwgYXR0ck5hbWU7XG4gICAgICAgICAgICBmcm9tVmFsdWUgPSBmcm9tTm9kZS5nZXRBdHRyaWJ1dGVOUyhhdHRyTmFtZXNwYWNlVVJJLCBhdHRyTmFtZSk7XG5cbiAgICAgICAgICAgIGlmIChmcm9tVmFsdWUgIT09IGF0dHJWYWx1ZSkge1xuICAgICAgICAgICAgICAgIGlmIChhdHRyLnByZWZpeCA9PT0gJ3htbG5zJyl7XG4gICAgICAgICAgICAgICAgICAgIGF0dHJOYW1lID0gYXR0ci5uYW1lOyAvLyBJdCdzIG5vdCBhbGxvd2VkIHRvIHNldCBhbiBhdHRyaWJ1dGUgd2l0aCB0aGUgWE1MTlMgbmFtZXNwYWNlIHdpdGhvdXQgc3BlY2lmeWluZyB0aGUgYHhtbG5zYCBwcmVmaXhcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgZnJvbU5vZGUuc2V0QXR0cmlidXRlTlMoYXR0ck5hbWVzcGFjZVVSSSwgYXR0ck5hbWUsIGF0dHJWYWx1ZSk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBmcm9tVmFsdWUgPSBmcm9tTm9kZS5nZXRBdHRyaWJ1dGUoYXR0ck5hbWUpO1xuXG4gICAgICAgICAgICBpZiAoZnJvbVZhbHVlICE9PSBhdHRyVmFsdWUpIHtcbiAgICAgICAgICAgICAgICBmcm9tTm9kZS5zZXRBdHRyaWJ1dGUoYXR0ck5hbWUsIGF0dHJWYWx1ZSk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBSZW1vdmUgYW55IGV4dHJhIGF0dHJpYnV0ZXMgZm91bmQgb24gdGhlIG9yaWdpbmFsIERPTSBlbGVtZW50IHRoYXRcbiAgICAvLyB3ZXJlbid0IGZvdW5kIG9uIHRoZSB0YXJnZXQgZWxlbWVudC5cbiAgICB2YXIgZnJvbU5vZGVBdHRycyA9IGZyb21Ob2RlLmF0dHJpYnV0ZXM7XG5cbiAgICBmb3IgKHZhciBkID0gZnJvbU5vZGVBdHRycy5sZW5ndGggLSAxOyBkID49IDA7IGQtLSkge1xuICAgICAgICBhdHRyID0gZnJvbU5vZGVBdHRyc1tkXTtcbiAgICAgICAgYXR0ck5hbWUgPSBhdHRyLm5hbWU7XG4gICAgICAgIGF0dHJOYW1lc3BhY2VVUkkgPSBhdHRyLm5hbWVzcGFjZVVSSTtcblxuICAgICAgICBpZiAoYXR0ck5hbWVzcGFjZVVSSSkge1xuICAgICAgICAgICAgYXR0ck5hbWUgPSBhdHRyLmxvY2FsTmFtZSB8fCBhdHRyTmFtZTtcblxuICAgICAgICAgICAgaWYgKCF0b05vZGUuaGFzQXR0cmlidXRlTlMoYXR0ck5hbWVzcGFjZVVSSSwgYXR0ck5hbWUpKSB7XG4gICAgICAgICAgICAgICAgZnJvbU5vZGUucmVtb3ZlQXR0cmlidXRlTlMoYXR0ck5hbWVzcGFjZVVSSSwgYXR0ck5hbWUpO1xuICAgICAgICAgICAgfVxuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgaWYgKCF0b05vZGUuaGFzQXR0cmlidXRlKGF0dHJOYW1lKSkge1xuICAgICAgICAgICAgICAgIGZyb21Ob2RlLnJlbW92ZUF0dHJpYnV0ZShhdHRyTmFtZSk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICB9XG59XG5cbnZhciByYW5nZTsgLy8gQ3JlYXRlIGEgcmFuZ2Ugb2JqZWN0IGZvciBlZmZpY2VudGx5IHJlbmRlcmluZyBzdHJpbmdzIHRvIGVsZW1lbnRzLlxudmFyIE5TX1hIVE1MID0gJ2h0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwnO1xuXG52YXIgZG9jID0gdHlwZW9mIGRvY3VtZW50ID09PSAndW5kZWZpbmVkJyA/IHVuZGVmaW5lZCA6IGRvY3VtZW50O1xudmFyIEhBU19URU1QTEFURV9TVVBQT1JUID0gISFkb2MgJiYgJ2NvbnRlbnQnIGluIGRvYy5jcmVhdGVFbGVtZW50KCd0ZW1wbGF0ZScpO1xudmFyIEhBU19SQU5HRV9TVVBQT1JUID0gISFkb2MgJiYgZG9jLmNyZWF0ZVJhbmdlICYmICdjcmVhdGVDb250ZXh0dWFsRnJhZ21lbnQnIGluIGRvYy5jcmVhdGVSYW5nZSgpO1xuXG5mdW5jdGlvbiBjcmVhdGVGcmFnbWVudEZyb21UZW1wbGF0ZShzdHIpIHtcbiAgICB2YXIgdGVtcGxhdGUgPSBkb2MuY3JlYXRlRWxlbWVudCgndGVtcGxhdGUnKTtcbiAgICB0ZW1wbGF0ZS5pbm5lckhUTUwgPSBzdHI7XG4gICAgcmV0dXJuIHRlbXBsYXRlLmNvbnRlbnQuY2hpbGROb2Rlc1swXTtcbn1cblxuZnVuY3Rpb24gY3JlYXRlRnJhZ21lbnRGcm9tUmFuZ2Uoc3RyKSB7XG4gICAgaWYgKCFyYW5nZSkge1xuICAgICAgICByYW5nZSA9IGRvYy5jcmVhdGVSYW5nZSgpO1xuICAgICAgICByYW5nZS5zZWxlY3ROb2RlKGRvYy5ib2R5KTtcbiAgICB9XG5cbiAgICB2YXIgZnJhZ21lbnQgPSByYW5nZS5jcmVhdGVDb250ZXh0dWFsRnJhZ21lbnQoc3RyKTtcbiAgICByZXR1cm4gZnJhZ21lbnQuY2hpbGROb2Rlc1swXTtcbn1cblxuZnVuY3Rpb24gY3JlYXRlRnJhZ21lbnRGcm9tV3JhcChzdHIpIHtcbiAgICB2YXIgZnJhZ21lbnQgPSBkb2MuY3JlYXRlRWxlbWVudCgnYm9keScpO1xuICAgIGZyYWdtZW50LmlubmVySFRNTCA9IHN0cjtcbiAgICByZXR1cm4gZnJhZ21lbnQuY2hpbGROb2Rlc1swXTtcbn1cblxuLyoqXG4gKiBUaGlzIGlzIGFib3V0IHRoZSBzYW1lXG4gKiB2YXIgaHRtbCA9IG5ldyBET01QYXJzZXIoKS5wYXJzZUZyb21TdHJpbmcoc3RyLCAndGV4dC9odG1sJyk7XG4gKiByZXR1cm4gaHRtbC5ib2R5LmZpcnN0Q2hpbGQ7XG4gKlxuICogQG1ldGhvZCB0b0VsZW1lbnRcbiAqIEBwYXJhbSB7U3RyaW5nfSBzdHJcbiAqL1xuZnVuY3Rpb24gdG9FbGVtZW50KHN0cikge1xuICAgIHN0ciA9IHN0ci50cmltKCk7XG4gICAgaWYgKEhBU19URU1QTEFURV9TVVBQT1JUKSB7XG4gICAgICAvLyBhdm9pZCByZXN0cmljdGlvbnMgb24gY29udGVudCBmb3IgdGhpbmdzIGxpa2UgYDx0cj48dGg+SGk8L3RoPjwvdHI+YCB3aGljaFxuICAgICAgLy8gY3JlYXRlQ29udGV4dHVhbEZyYWdtZW50IGRvZXNuJ3Qgc3VwcG9ydFxuICAgICAgLy8gPHRlbXBsYXRlPiBzdXBwb3J0IG5vdCBhdmFpbGFibGUgaW4gSUVcbiAgICAgIHJldHVybiBjcmVhdGVGcmFnbWVudEZyb21UZW1wbGF0ZShzdHIpO1xuICAgIH0gZWxzZSBpZiAoSEFTX1JBTkdFX1NVUFBPUlQpIHtcbiAgICAgIHJldHVybiBjcmVhdGVGcmFnbWVudEZyb21SYW5nZShzdHIpO1xuICAgIH1cblxuICAgIHJldHVybiBjcmVhdGVGcmFnbWVudEZyb21XcmFwKHN0cik7XG59XG5cbi8qKlxuICogUmV0dXJucyB0cnVlIGlmIHR3byBub2RlJ3MgbmFtZXMgYXJlIHRoZSBzYW1lLlxuICpcbiAqIE5PVEU6IFdlIGRvbid0IGJvdGhlciBjaGVja2luZyBgbmFtZXNwYWNlVVJJYCBiZWNhdXNlIHlvdSB3aWxsIG5ldmVyIGZpbmQgdHdvIEhUTUwgZWxlbWVudHMgd2l0aCB0aGUgc2FtZVxuICogICAgICAgbm9kZU5hbWUgYW5kIGRpZmZlcmVudCBuYW1lc3BhY2UgVVJJcy5cbiAqXG4gKiBAcGFyYW0ge0VsZW1lbnR9IGFcbiAqIEBwYXJhbSB7RWxlbWVudH0gYiBUaGUgdGFyZ2V0IGVsZW1lbnRcbiAqIEByZXR1cm4ge2Jvb2xlYW59XG4gKi9cbmZ1bmN0aW9uIGNvbXBhcmVOb2RlTmFtZXMoZnJvbUVsLCB0b0VsKSB7XG4gICAgdmFyIGZyb21Ob2RlTmFtZSA9IGZyb21FbC5ub2RlTmFtZTtcbiAgICB2YXIgdG9Ob2RlTmFtZSA9IHRvRWwubm9kZU5hbWU7XG4gICAgdmFyIGZyb21Db2RlU3RhcnQsIHRvQ29kZVN0YXJ0O1xuXG4gICAgaWYgKGZyb21Ob2RlTmFtZSA9PT0gdG9Ob2RlTmFtZSkge1xuICAgICAgICByZXR1cm4gdHJ1ZTtcbiAgICB9XG5cbiAgICBmcm9tQ29kZVN0YXJ0ID0gZnJvbU5vZGVOYW1lLmNoYXJDb2RlQXQoMCk7XG4gICAgdG9Db2RlU3RhcnQgPSB0b05vZGVOYW1lLmNoYXJDb2RlQXQoMCk7XG5cbiAgICAvLyBJZiB0aGUgdGFyZ2V0IGVsZW1lbnQgaXMgYSB2aXJ0dWFsIERPTSBub2RlIG9yIFNWRyBub2RlIHRoZW4gd2UgbWF5XG4gICAgLy8gbmVlZCB0byBub3JtYWxpemUgdGhlIHRhZyBuYW1lIGJlZm9yZSBjb21wYXJpbmcuIE5vcm1hbCBIVE1MIGVsZW1lbnRzIHRoYXQgYXJlXG4gICAgLy8gaW4gdGhlIFwiaHR0cDovL3d3dy53My5vcmcvMTk5OS94aHRtbFwiXG4gICAgLy8gYXJlIGNvbnZlcnRlZCB0byB1cHBlciBjYXNlXG4gICAgaWYgKGZyb21Db2RlU3RhcnQgPD0gOTAgJiYgdG9Db2RlU3RhcnQgPj0gOTcpIHsgLy8gZnJvbSBpcyB1cHBlciBhbmQgdG8gaXMgbG93ZXJcbiAgICAgICAgcmV0dXJuIGZyb21Ob2RlTmFtZSA9PT0gdG9Ob2RlTmFtZS50b1VwcGVyQ2FzZSgpO1xuICAgIH0gZWxzZSBpZiAodG9Db2RlU3RhcnQgPD0gOTAgJiYgZnJvbUNvZGVTdGFydCA+PSA5NykgeyAvLyB0byBpcyB1cHBlciBhbmQgZnJvbSBpcyBsb3dlclxuICAgICAgICByZXR1cm4gdG9Ob2RlTmFtZSA9PT0gZnJvbU5vZGVOYW1lLnRvVXBwZXJDYXNlKCk7XG4gICAgfSBlbHNlIHtcbiAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgIH1cbn1cblxuLyoqXG4gKiBDcmVhdGUgYW4gZWxlbWVudCwgb3B0aW9uYWxseSB3aXRoIGEga25vd24gbmFtZXNwYWNlIFVSSS5cbiAqXG4gKiBAcGFyYW0ge3N0cmluZ30gbmFtZSB0aGUgZWxlbWVudCBuYW1lLCBlLmcuICdkaXYnIG9yICdzdmcnXG4gKiBAcGFyYW0ge3N0cmluZ30gW25hbWVzcGFjZVVSSV0gdGhlIGVsZW1lbnQncyBuYW1lc3BhY2UgVVJJLCBpLmUuIHRoZSB2YWx1ZSBvZlxuICogaXRzIGB4bWxuc2AgYXR0cmlidXRlIG9yIGl0cyBpbmZlcnJlZCBuYW1lc3BhY2UuXG4gKlxuICogQHJldHVybiB7RWxlbWVudH1cbiAqL1xuZnVuY3Rpb24gY3JlYXRlRWxlbWVudE5TKG5hbWUsIG5hbWVzcGFjZVVSSSkge1xuICAgIHJldHVybiAhbmFtZXNwYWNlVVJJIHx8IG5hbWVzcGFjZVVSSSA9PT0gTlNfWEhUTUwgP1xuICAgICAgICBkb2MuY3JlYXRlRWxlbWVudChuYW1lKSA6XG4gICAgICAgIGRvYy5jcmVhdGVFbGVtZW50TlMobmFtZXNwYWNlVVJJLCBuYW1lKTtcbn1cblxuLyoqXG4gKiBDb3BpZXMgdGhlIGNoaWxkcmVuIG9mIG9uZSBET00gZWxlbWVudCB0byBhbm90aGVyIERPTSBlbGVtZW50XG4gKi9cbmZ1bmN0aW9uIG1vdmVDaGlsZHJlbihmcm9tRWwsIHRvRWwpIHtcbiAgICB2YXIgY3VyQ2hpbGQgPSBmcm9tRWwuZmlyc3RDaGlsZDtcbiAgICB3aGlsZSAoY3VyQ2hpbGQpIHtcbiAgICAgICAgdmFyIG5leHRDaGlsZCA9IGN1ckNoaWxkLm5leHRTaWJsaW5nO1xuICAgICAgICB0b0VsLmFwcGVuZENoaWxkKGN1ckNoaWxkKTtcbiAgICAgICAgY3VyQ2hpbGQgPSBuZXh0Q2hpbGQ7XG4gICAgfVxuICAgIHJldHVybiB0b0VsO1xufVxuXG5mdW5jdGlvbiBzeW5jQm9vbGVhbkF0dHJQcm9wKGZyb21FbCwgdG9FbCwgbmFtZSkge1xuICAgIGlmIChmcm9tRWxbbmFtZV0gIT09IHRvRWxbbmFtZV0pIHtcbiAgICAgICAgZnJvbUVsW25hbWVdID0gdG9FbFtuYW1lXTtcbiAgICAgICAgaWYgKGZyb21FbFtuYW1lXSkge1xuICAgICAgICAgICAgZnJvbUVsLnNldEF0dHJpYnV0ZShuYW1lLCAnJyk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBmcm9tRWwucmVtb3ZlQXR0cmlidXRlKG5hbWUpO1xuICAgICAgICB9XG4gICAgfVxufVxuXG52YXIgc3BlY2lhbEVsSGFuZGxlcnMgPSB7XG4gICAgT1BUSU9OOiBmdW5jdGlvbihmcm9tRWwsIHRvRWwpIHtcbiAgICAgICAgdmFyIHBhcmVudE5vZGUgPSBmcm9tRWwucGFyZW50Tm9kZTtcbiAgICAgICAgaWYgKHBhcmVudE5vZGUpIHtcbiAgICAgICAgICAgIHZhciBwYXJlbnROYW1lID0gcGFyZW50Tm9kZS5ub2RlTmFtZS50b1VwcGVyQ2FzZSgpO1xuICAgICAgICAgICAgaWYgKHBhcmVudE5hbWUgPT09ICdPUFRHUk9VUCcpIHtcbiAgICAgICAgICAgICAgICBwYXJlbnROb2RlID0gcGFyZW50Tm9kZS5wYXJlbnROb2RlO1xuICAgICAgICAgICAgICAgIHBhcmVudE5hbWUgPSBwYXJlbnROb2RlICYmIHBhcmVudE5vZGUubm9kZU5hbWUudG9VcHBlckNhc2UoKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGlmIChwYXJlbnROYW1lID09PSAnU0VMRUNUJyAmJiAhcGFyZW50Tm9kZS5oYXNBdHRyaWJ1dGUoJ211bHRpcGxlJykpIHtcbiAgICAgICAgICAgICAgICBpZiAoZnJvbUVsLmhhc0F0dHJpYnV0ZSgnc2VsZWN0ZWQnKSAmJiAhdG9FbC5zZWxlY3RlZCkge1xuICAgICAgICAgICAgICAgICAgICAvLyBXb3JrYXJvdW5kIGZvciBNUyBFZGdlIGJ1ZyB3aGVyZSB0aGUgJ3NlbGVjdGVkJyBhdHRyaWJ1dGUgY2FuIG9ubHkgYmVcbiAgICAgICAgICAgICAgICAgICAgLy8gcmVtb3ZlZCBpZiBzZXQgdG8gYSBub24tZW1wdHkgdmFsdWU6XG4gICAgICAgICAgICAgICAgICAgIC8vIGh0dHBzOi8vZGV2ZWxvcGVyLm1pY3Jvc29mdC5jb20vZW4tdXMvbWljcm9zb2Z0LWVkZ2UvcGxhdGZvcm0vaXNzdWVzLzEyMDg3Njc5L1xuICAgICAgICAgICAgICAgICAgICBmcm9tRWwuc2V0QXR0cmlidXRlKCdzZWxlY3RlZCcsICdzZWxlY3RlZCcpO1xuICAgICAgICAgICAgICAgICAgICBmcm9tRWwucmVtb3ZlQXR0cmlidXRlKCdzZWxlY3RlZCcpO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAvLyBXZSBoYXZlIHRvIHJlc2V0IHNlbGVjdCBlbGVtZW50J3Mgc2VsZWN0ZWRJbmRleCB0byAtMSwgb3RoZXJ3aXNlIHNldHRpbmdcbiAgICAgICAgICAgICAgICAvLyBmcm9tRWwuc2VsZWN0ZWQgdXNpbmcgdGhlIHN5bmNCb29sZWFuQXR0clByb3AgYmVsb3cgaGFzIG5vIGVmZmVjdC5cbiAgICAgICAgICAgICAgICAvLyBUaGUgY29ycmVjdCBzZWxlY3RlZEluZGV4IHdpbGwgYmUgc2V0IGluIHRoZSBTRUxFQ1Qgc3BlY2lhbCBoYW5kbGVyIGJlbG93LlxuICAgICAgICAgICAgICAgIHBhcmVudE5vZGUuc2VsZWN0ZWRJbmRleCA9IC0xO1xuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICAgIHN5bmNCb29sZWFuQXR0clByb3AoZnJvbUVsLCB0b0VsLCAnc2VsZWN0ZWQnKTtcbiAgICB9LFxuICAgIC8qKlxuICAgICAqIFRoZSBcInZhbHVlXCIgYXR0cmlidXRlIGlzIHNwZWNpYWwgZm9yIHRoZSA8aW5wdXQ+IGVsZW1lbnQgc2luY2UgaXQgc2V0c1xuICAgICAqIHRoZSBpbml0aWFsIHZhbHVlLiBDaGFuZ2luZyB0aGUgXCJ2YWx1ZVwiIGF0dHJpYnV0ZSB3aXRob3V0IGNoYW5naW5nIHRoZVxuICAgICAqIFwidmFsdWVcIiBwcm9wZXJ0eSB3aWxsIGhhdmUgbm8gZWZmZWN0IHNpbmNlIGl0IGlzIG9ubHkgdXNlZCB0byB0aGUgc2V0IHRoZVxuICAgICAqIGluaXRpYWwgdmFsdWUuICBTaW1pbGFyIGZvciB0aGUgXCJjaGVja2VkXCIgYXR0cmlidXRlLCBhbmQgXCJkaXNhYmxlZFwiLlxuICAgICAqL1xuICAgIElOUFVUOiBmdW5jdGlvbihmcm9tRWwsIHRvRWwpIHtcbiAgICAgICAgc3luY0Jvb2xlYW5BdHRyUHJvcChmcm9tRWwsIHRvRWwsICdjaGVja2VkJyk7XG4gICAgICAgIHN5bmNCb29sZWFuQXR0clByb3AoZnJvbUVsLCB0b0VsLCAnZGlzYWJsZWQnKTtcblxuICAgICAgICBpZiAoZnJvbUVsLnZhbHVlICE9PSB0b0VsLnZhbHVlKSB7XG4gICAgICAgICAgICBmcm9tRWwudmFsdWUgPSB0b0VsLnZhbHVlO1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCF0b0VsLmhhc0F0dHJpYnV0ZSgndmFsdWUnKSkge1xuICAgICAgICAgICAgZnJvbUVsLnJlbW92ZUF0dHJpYnV0ZSgndmFsdWUnKTtcbiAgICAgICAgfVxuICAgIH0sXG5cbiAgICBURVhUQVJFQTogZnVuY3Rpb24oZnJvbUVsLCB0b0VsKSB7XG4gICAgICAgIHZhciBuZXdWYWx1ZSA9IHRvRWwudmFsdWU7XG4gICAgICAgIGlmIChmcm9tRWwudmFsdWUgIT09IG5ld1ZhbHVlKSB7XG4gICAgICAgICAgICBmcm9tRWwudmFsdWUgPSBuZXdWYWx1ZTtcbiAgICAgICAgfVxuXG4gICAgICAgIHZhciBmaXJzdENoaWxkID0gZnJvbUVsLmZpcnN0Q2hpbGQ7XG4gICAgICAgIGlmIChmaXJzdENoaWxkKSB7XG4gICAgICAgICAgICAvLyBOZWVkZWQgZm9yIElFLiBBcHBhcmVudGx5IElFIHNldHMgdGhlIHBsYWNlaG9sZGVyIGFzIHRoZVxuICAgICAgICAgICAgLy8gbm9kZSB2YWx1ZSBhbmQgdmlzZSB2ZXJzYS4gVGhpcyBpZ25vcmVzIGFuIGVtcHR5IHVwZGF0ZS5cbiAgICAgICAgICAgIHZhciBvbGRWYWx1ZSA9IGZpcnN0Q2hpbGQubm9kZVZhbHVlO1xuXG4gICAgICAgICAgICBpZiAob2xkVmFsdWUgPT0gbmV3VmFsdWUgfHwgKCFuZXdWYWx1ZSAmJiBvbGRWYWx1ZSA9PSBmcm9tRWwucGxhY2Vob2xkZXIpKSB7XG4gICAgICAgICAgICAgICAgcmV0dXJuO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBmaXJzdENoaWxkLm5vZGVWYWx1ZSA9IG5ld1ZhbHVlO1xuICAgICAgICB9XG4gICAgfSxcbiAgICBTRUxFQ1Q6IGZ1bmN0aW9uKGZyb21FbCwgdG9FbCkge1xuICAgICAgICBpZiAoIXRvRWwuaGFzQXR0cmlidXRlKCdtdWx0aXBsZScpKSB7XG4gICAgICAgICAgICB2YXIgc2VsZWN0ZWRJbmRleCA9IC0xO1xuICAgICAgICAgICAgdmFyIGkgPSAwO1xuICAgICAgICAgICAgLy8gV2UgaGF2ZSB0byBsb29wIHRocm91Z2ggY2hpbGRyZW4gb2YgZnJvbUVsLCBub3QgdG9FbCBzaW5jZSBub2RlcyBjYW4gYmUgbW92ZWRcbiAgICAgICAgICAgIC8vIGZyb20gdG9FbCB0byBmcm9tRWwgZGlyZWN0bHkgd2hlbiBtb3JwaGluZy5cbiAgICAgICAgICAgIC8vIEF0IHRoZSB0aW1lIHRoaXMgc3BlY2lhbCBoYW5kbGVyIGlzIGludm9rZWQsIGFsbCBjaGlsZHJlbiBoYXZlIGFscmVhZHkgYmVlbiBtb3JwaGVkXG4gICAgICAgICAgICAvLyBhbmQgYXBwZW5kZWQgdG8gLyByZW1vdmVkIGZyb20gZnJvbUVsLCBzbyB1c2luZyBmcm9tRWwgaGVyZSBpcyBzYWZlIGFuZCBjb3JyZWN0LlxuICAgICAgICAgICAgdmFyIGN1ckNoaWxkID0gZnJvbUVsLmZpcnN0Q2hpbGQ7XG4gICAgICAgICAgICB2YXIgb3B0Z3JvdXA7XG4gICAgICAgICAgICB2YXIgbm9kZU5hbWU7XG4gICAgICAgICAgICB3aGlsZShjdXJDaGlsZCkge1xuICAgICAgICAgICAgICAgIG5vZGVOYW1lID0gY3VyQ2hpbGQubm9kZU5hbWUgJiYgY3VyQ2hpbGQubm9kZU5hbWUudG9VcHBlckNhc2UoKTtcbiAgICAgICAgICAgICAgICBpZiAobm9kZU5hbWUgPT09ICdPUFRHUk9VUCcpIHtcbiAgICAgICAgICAgICAgICAgICAgb3B0Z3JvdXAgPSBjdXJDaGlsZDtcbiAgICAgICAgICAgICAgICAgICAgY3VyQ2hpbGQgPSBvcHRncm91cC5maXJzdENoaWxkO1xuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIGlmIChub2RlTmFtZSA9PT0gJ09QVElPTicpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGlmIChjdXJDaGlsZC5oYXNBdHRyaWJ1dGUoJ3NlbGVjdGVkJykpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZWxlY3RlZEluZGV4ID0gaTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgIGkrKztcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICBjdXJDaGlsZCA9IGN1ckNoaWxkLm5leHRTaWJsaW5nO1xuICAgICAgICAgICAgICAgICAgICBpZiAoIWN1ckNoaWxkICYmIG9wdGdyb3VwKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBjdXJDaGlsZCA9IG9wdGdyb3VwLm5leHRTaWJsaW5nO1xuICAgICAgICAgICAgICAgICAgICAgICAgb3B0Z3JvdXAgPSBudWxsO1xuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBmcm9tRWwuc2VsZWN0ZWRJbmRleCA9IHNlbGVjdGVkSW5kZXg7XG4gICAgICAgIH1cbiAgICB9XG59O1xuXG52YXIgRUxFTUVOVF9OT0RFID0gMTtcbnZhciBET0NVTUVOVF9GUkFHTUVOVF9OT0RFJDEgPSAxMTtcbnZhciBURVhUX05PREUgPSAzO1xudmFyIENPTU1FTlRfTk9ERSA9IDg7XG5cbmZ1bmN0aW9uIG5vb3AoKSB7fVxuXG5mdW5jdGlvbiBkZWZhdWx0R2V0Tm9kZUtleShub2RlKSB7XG4gIGlmIChub2RlKSB7XG4gICAgcmV0dXJuIChub2RlLmdldEF0dHJpYnV0ZSAmJiBub2RlLmdldEF0dHJpYnV0ZSgnaWQnKSkgfHwgbm9kZS5pZDtcbiAgfVxufVxuXG5mdW5jdGlvbiBtb3JwaGRvbUZhY3RvcnkobW9ycGhBdHRycykge1xuXG4gIHJldHVybiBmdW5jdGlvbiBtb3JwaGRvbShmcm9tTm9kZSwgdG9Ob2RlLCBvcHRpb25zKSB7XG4gICAgaWYgKCFvcHRpb25zKSB7XG4gICAgICBvcHRpb25zID0ge307XG4gICAgfVxuXG4gICAgaWYgKHR5cGVvZiB0b05vZGUgPT09ICdzdHJpbmcnKSB7XG4gICAgICBpZiAoZnJvbU5vZGUubm9kZU5hbWUgPT09ICcjZG9jdW1lbnQnIHx8IGZyb21Ob2RlLm5vZGVOYW1lID09PSAnSFRNTCcgfHwgZnJvbU5vZGUubm9kZU5hbWUgPT09ICdCT0RZJykge1xuICAgICAgICB2YXIgdG9Ob2RlSHRtbCA9IHRvTm9kZTtcbiAgICAgICAgdG9Ob2RlID0gZG9jLmNyZWF0ZUVsZW1lbnQoJ2h0bWwnKTtcbiAgICAgICAgdG9Ob2RlLmlubmVySFRNTCA9IHRvTm9kZUh0bWw7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB0b05vZGUgPSB0b0VsZW1lbnQodG9Ob2RlKTtcbiAgICAgIH1cbiAgICB9IGVsc2UgaWYgKHRvTm9kZS5ub2RlVHlwZSA9PT0gRE9DVU1FTlRfRlJBR01FTlRfTk9ERSQxKSB7XG4gICAgICB0b05vZGUgPSB0b05vZGUuZmlyc3RFbGVtZW50Q2hpbGQ7XG4gICAgfVxuXG4gICAgdmFyIGdldE5vZGVLZXkgPSBvcHRpb25zLmdldE5vZGVLZXkgfHwgZGVmYXVsdEdldE5vZGVLZXk7XG4gICAgdmFyIG9uQmVmb3JlTm9kZUFkZGVkID0gb3B0aW9ucy5vbkJlZm9yZU5vZGVBZGRlZCB8fCBub29wO1xuICAgIHZhciBvbk5vZGVBZGRlZCA9IG9wdGlvbnMub25Ob2RlQWRkZWQgfHwgbm9vcDtcbiAgICB2YXIgb25CZWZvcmVFbFVwZGF0ZWQgPSBvcHRpb25zLm9uQmVmb3JlRWxVcGRhdGVkIHx8IG5vb3A7XG4gICAgdmFyIG9uRWxVcGRhdGVkID0gb3B0aW9ucy5vbkVsVXBkYXRlZCB8fCBub29wO1xuICAgIHZhciBvbkJlZm9yZU5vZGVEaXNjYXJkZWQgPSBvcHRpb25zLm9uQmVmb3JlTm9kZURpc2NhcmRlZCB8fCBub29wO1xuICAgIHZhciBvbk5vZGVEaXNjYXJkZWQgPSBvcHRpb25zLm9uTm9kZURpc2NhcmRlZCB8fCBub29wO1xuICAgIHZhciBvbkJlZm9yZUVsQ2hpbGRyZW5VcGRhdGVkID0gb3B0aW9ucy5vbkJlZm9yZUVsQ2hpbGRyZW5VcGRhdGVkIHx8IG5vb3A7XG4gICAgdmFyIHNraXBGcm9tQ2hpbGRyZW4gPSBvcHRpb25zLnNraXBGcm9tQ2hpbGRyZW4gfHwgbm9vcDtcbiAgICB2YXIgYWRkQ2hpbGQgPSBvcHRpb25zLmFkZENoaWxkIHx8IGZ1bmN0aW9uKHBhcmVudCwgY2hpbGQpeyByZXR1cm4gcGFyZW50LmFwcGVuZENoaWxkKGNoaWxkKTsgfTtcbiAgICB2YXIgY2hpbGRyZW5Pbmx5ID0gb3B0aW9ucy5jaGlsZHJlbk9ubHkgPT09IHRydWU7XG5cbiAgICAvLyBUaGlzIG9iamVjdCBpcyB1c2VkIGFzIGEgbG9va3VwIHRvIHF1aWNrbHkgZmluZCBhbGwga2V5ZWQgZWxlbWVudHMgaW4gdGhlIG9yaWdpbmFsIERPTSB0cmVlLlxuICAgIHZhciBmcm9tTm9kZXNMb29rdXAgPSBPYmplY3QuY3JlYXRlKG51bGwpO1xuICAgIHZhciBrZXllZFJlbW92YWxMaXN0ID0gW107XG5cbiAgICBmdW5jdGlvbiBhZGRLZXllZFJlbW92YWwoa2V5KSB7XG4gICAgICBrZXllZFJlbW92YWxMaXN0LnB1c2goa2V5KTtcbiAgICB9XG5cbiAgICBmdW5jdGlvbiB3YWxrRGlzY2FyZGVkQ2hpbGROb2Rlcyhub2RlLCBza2lwS2V5ZWROb2Rlcykge1xuICAgICAgaWYgKG5vZGUubm9kZVR5cGUgPT09IEVMRU1FTlRfTk9ERSkge1xuICAgICAgICB2YXIgY3VyQ2hpbGQgPSBub2RlLmZpcnN0Q2hpbGQ7XG4gICAgICAgIHdoaWxlIChjdXJDaGlsZCkge1xuXG4gICAgICAgICAgdmFyIGtleSA9IHVuZGVmaW5lZDtcblxuICAgICAgICAgIGlmIChza2lwS2V5ZWROb2RlcyAmJiAoa2V5ID0gZ2V0Tm9kZUtleShjdXJDaGlsZCkpKSB7XG4gICAgICAgICAgICAvLyBJZiB3ZSBhcmUgc2tpcHBpbmcga2V5ZWQgbm9kZXMgdGhlbiB3ZSBhZGQgdGhlIGtleVxuICAgICAgICAgICAgLy8gdG8gYSBsaXN0IHNvIHRoYXQgaXQgY2FuIGJlIGhhbmRsZWQgYXQgdGhlIHZlcnkgZW5kLlxuICAgICAgICAgICAgYWRkS2V5ZWRSZW1vdmFsKGtleSk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIC8vIE9ubHkgcmVwb3J0IHRoZSBub2RlIGFzIGRpc2NhcmRlZCBpZiBpdCBpcyBub3Qga2V5ZWQuIFdlIGRvIHRoaXMgYmVjYXVzZVxuICAgICAgICAgICAgLy8gYXQgdGhlIGVuZCB3ZSBsb29wIHRocm91Z2ggYWxsIGtleWVkIGVsZW1lbnRzIHRoYXQgd2VyZSB1bm1hdGNoZWRcbiAgICAgICAgICAgIC8vIGFuZCB0aGVuIGRpc2NhcmQgdGhlbSBpbiBvbmUgZmluYWwgcGFzcy5cbiAgICAgICAgICAgIG9uTm9kZURpc2NhcmRlZChjdXJDaGlsZCk7XG4gICAgICAgICAgICBpZiAoY3VyQ2hpbGQuZmlyc3RDaGlsZCkge1xuICAgICAgICAgICAgICB3YWxrRGlzY2FyZGVkQ2hpbGROb2RlcyhjdXJDaGlsZCwgc2tpcEtleWVkTm9kZXMpO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cblxuICAgICAgICAgIGN1ckNoaWxkID0gY3VyQ2hpbGQubmV4dFNpYmxpbmc7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICAvKipcbiAgICAqIFJlbW92ZXMgYSBET00gbm9kZSBvdXQgb2YgdGhlIG9yaWdpbmFsIERPTVxuICAgICpcbiAgICAqIEBwYXJhbSAge05vZGV9IG5vZGUgVGhlIG5vZGUgdG8gcmVtb3ZlXG4gICAgKiBAcGFyYW0gIHtOb2RlfSBwYXJlbnROb2RlIFRoZSBub2RlcyBwYXJlbnRcbiAgICAqIEBwYXJhbSAge0Jvb2xlYW59IHNraXBLZXllZE5vZGVzIElmIHRydWUgdGhlbiBlbGVtZW50cyB3aXRoIGtleXMgd2lsbCBiZSBza2lwcGVkIGFuZCBub3QgZGlzY2FyZGVkLlxuICAgICogQHJldHVybiB7dW5kZWZpbmVkfVxuICAgICovXG4gICAgZnVuY3Rpb24gcmVtb3ZlTm9kZShub2RlLCBwYXJlbnROb2RlLCBza2lwS2V5ZWROb2Rlcykge1xuICAgICAgaWYgKG9uQmVmb3JlTm9kZURpc2NhcmRlZChub2RlKSA9PT0gZmFsc2UpIHtcbiAgICAgICAgcmV0dXJuO1xuICAgICAgfVxuXG4gICAgICBpZiAocGFyZW50Tm9kZSkge1xuICAgICAgICBwYXJlbnROb2RlLnJlbW92ZUNoaWxkKG5vZGUpO1xuICAgICAgfVxuXG4gICAgICBvbk5vZGVEaXNjYXJkZWQobm9kZSk7XG4gICAgICB3YWxrRGlzY2FyZGVkQ2hpbGROb2Rlcyhub2RlLCBza2lwS2V5ZWROb2Rlcyk7XG4gICAgfVxuXG4gICAgLy8gLy8gVHJlZVdhbGtlciBpbXBsZW1lbnRhdGlvbiBpcyBubyBmYXN0ZXIsIGJ1dCBrZWVwaW5nIHRoaXMgYXJvdW5kIGluIGNhc2UgdGhpcyBjaGFuZ2VzIGluIHRoZSBmdXR1cmVcbiAgICAvLyBmdW5jdGlvbiBpbmRleFRyZWUocm9vdCkge1xuICAgIC8vICAgICB2YXIgdHJlZVdhbGtlciA9IGRvY3VtZW50LmNyZWF0ZVRyZWVXYWxrZXIoXG4gICAgLy8gICAgICAgICByb290LFxuICAgIC8vICAgICAgICAgTm9kZUZpbHRlci5TSE9XX0VMRU1FTlQpO1xuICAgIC8vXG4gICAgLy8gICAgIHZhciBlbDtcbiAgICAvLyAgICAgd2hpbGUoKGVsID0gdHJlZVdhbGtlci5uZXh0Tm9kZSgpKSkge1xuICAgIC8vICAgICAgICAgdmFyIGtleSA9IGdldE5vZGVLZXkoZWwpO1xuICAgIC8vICAgICAgICAgaWYgKGtleSkge1xuICAgIC8vICAgICAgICAgICAgIGZyb21Ob2Rlc0xvb2t1cFtrZXldID0gZWw7XG4gICAgLy8gICAgICAgICB9XG4gICAgLy8gICAgIH1cbiAgICAvLyB9XG5cbiAgICAvLyAvLyBOb2RlSXRlcmF0b3IgaW1wbGVtZW50YXRpb24gaXMgbm8gZmFzdGVyLCBidXQga2VlcGluZyB0aGlzIGFyb3VuZCBpbiBjYXNlIHRoaXMgY2hhbmdlcyBpbiB0aGUgZnV0dXJlXG4gICAgLy9cbiAgICAvLyBmdW5jdGlvbiBpbmRleFRyZWUobm9kZSkge1xuICAgIC8vICAgICB2YXIgbm9kZUl0ZXJhdG9yID0gZG9jdW1lbnQuY3JlYXRlTm9kZUl0ZXJhdG9yKG5vZGUsIE5vZGVGaWx0ZXIuU0hPV19FTEVNRU5UKTtcbiAgICAvLyAgICAgdmFyIGVsO1xuICAgIC8vICAgICB3aGlsZSgoZWwgPSBub2RlSXRlcmF0b3IubmV4dE5vZGUoKSkpIHtcbiAgICAvLyAgICAgICAgIHZhciBrZXkgPSBnZXROb2RlS2V5KGVsKTtcbiAgICAvLyAgICAgICAgIGlmIChrZXkpIHtcbiAgICAvLyAgICAgICAgICAgICBmcm9tTm9kZXNMb29rdXBba2V5XSA9IGVsO1xuICAgIC8vICAgICAgICAgfVxuICAgIC8vICAgICB9XG4gICAgLy8gfVxuXG4gICAgZnVuY3Rpb24gaW5kZXhUcmVlKG5vZGUpIHtcbiAgICAgIGlmIChub2RlLm5vZGVUeXBlID09PSBFTEVNRU5UX05PREUgfHwgbm9kZS5ub2RlVHlwZSA9PT0gRE9DVU1FTlRfRlJBR01FTlRfTk9ERSQxKSB7XG4gICAgICAgIHZhciBjdXJDaGlsZCA9IG5vZGUuZmlyc3RDaGlsZDtcbiAgICAgICAgd2hpbGUgKGN1ckNoaWxkKSB7XG4gICAgICAgICAgdmFyIGtleSA9IGdldE5vZGVLZXkoY3VyQ2hpbGQpO1xuICAgICAgICAgIGlmIChrZXkpIHtcbiAgICAgICAgICAgIGZyb21Ob2Rlc0xvb2t1cFtrZXldID0gY3VyQ2hpbGQ7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgLy8gV2FsayByZWN1cnNpdmVseVxuICAgICAgICAgIGluZGV4VHJlZShjdXJDaGlsZCk7XG5cbiAgICAgICAgICBjdXJDaGlsZCA9IGN1ckNoaWxkLm5leHRTaWJsaW5nO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfVxuXG4gICAgaW5kZXhUcmVlKGZyb21Ob2RlKTtcblxuICAgIGZ1bmN0aW9uIGhhbmRsZU5vZGVBZGRlZChlbCkge1xuICAgICAgb25Ob2RlQWRkZWQoZWwpO1xuXG4gICAgICB2YXIgY3VyQ2hpbGQgPSBlbC5maXJzdENoaWxkO1xuICAgICAgd2hpbGUgKGN1ckNoaWxkKSB7XG4gICAgICAgIHZhciBuZXh0U2libGluZyA9IGN1ckNoaWxkLm5leHRTaWJsaW5nO1xuXG4gICAgICAgIHZhciBrZXkgPSBnZXROb2RlS2V5KGN1ckNoaWxkKTtcbiAgICAgICAgaWYgKGtleSkge1xuICAgICAgICAgIHZhciB1bm1hdGNoZWRGcm9tRWwgPSBmcm9tTm9kZXNMb29rdXBba2V5XTtcbiAgICAgICAgICAvLyBpZiB3ZSBmaW5kIGEgZHVwbGljYXRlICNpZCBub2RlIGluIGNhY2hlLCByZXBsYWNlIGBlbGAgd2l0aCBjYWNoZSB2YWx1ZVxuICAgICAgICAgIC8vIGFuZCBtb3JwaCBpdCB0byB0aGUgY2hpbGQgbm9kZS5cbiAgICAgICAgICBpZiAodW5tYXRjaGVkRnJvbUVsICYmIGNvbXBhcmVOb2RlTmFtZXMoY3VyQ2hpbGQsIHVubWF0Y2hlZEZyb21FbCkpIHtcbiAgICAgICAgICAgIGN1ckNoaWxkLnBhcmVudE5vZGUucmVwbGFjZUNoaWxkKHVubWF0Y2hlZEZyb21FbCwgY3VyQ2hpbGQpO1xuICAgICAgICAgICAgbW9ycGhFbCh1bm1hdGNoZWRGcm9tRWwsIGN1ckNoaWxkKTtcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgaGFuZGxlTm9kZUFkZGVkKGN1ckNoaWxkKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgLy8gcmVjdXJzaXZlbHkgY2FsbCBmb3IgY3VyQ2hpbGQgYW5kIGl0J3MgY2hpbGRyZW4gdG8gc2VlIGlmIHdlIGZpbmQgc29tZXRoaW5nIGluXG4gICAgICAgICAgLy8gZnJvbU5vZGVzTG9va3VwXG4gICAgICAgICAgaGFuZGxlTm9kZUFkZGVkKGN1ckNoaWxkKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGN1ckNoaWxkID0gbmV4dFNpYmxpbmc7XG4gICAgICB9XG4gICAgfVxuXG4gICAgZnVuY3Rpb24gY2xlYW51cEZyb21FbChmcm9tRWwsIGN1ckZyb21Ob2RlQ2hpbGQsIGN1ckZyb21Ob2RlS2V5KSB7XG4gICAgICAvLyBXZSBoYXZlIHByb2Nlc3NlZCBhbGwgb2YgdGhlIFwidG8gbm9kZXNcIi4gSWYgY3VyRnJvbU5vZGVDaGlsZCBpc1xuICAgICAgLy8gbm9uLW51bGwgdGhlbiB3ZSBzdGlsbCBoYXZlIHNvbWUgZnJvbSBub2RlcyBsZWZ0IG92ZXIgdGhhdCBuZWVkXG4gICAgICAvLyB0byBiZSByZW1vdmVkXG4gICAgICB3aGlsZSAoY3VyRnJvbU5vZGVDaGlsZCkge1xuICAgICAgICB2YXIgZnJvbU5leHRTaWJsaW5nID0gY3VyRnJvbU5vZGVDaGlsZC5uZXh0U2libGluZztcbiAgICAgICAgaWYgKChjdXJGcm9tTm9kZUtleSA9IGdldE5vZGVLZXkoY3VyRnJvbU5vZGVDaGlsZCkpKSB7XG4gICAgICAgICAgLy8gU2luY2UgdGhlIG5vZGUgaXMga2V5ZWQgaXQgbWlnaHQgYmUgbWF0Y2hlZCB1cCBsYXRlciBzbyB3ZSBkZWZlclxuICAgICAgICAgIC8vIHRoZSBhY3R1YWwgcmVtb3ZhbCB0byBsYXRlclxuICAgICAgICAgIGFkZEtleWVkUmVtb3ZhbChjdXJGcm9tTm9kZUtleSk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgLy8gTk9URTogd2Ugc2tpcCBuZXN0ZWQga2V5ZWQgbm9kZXMgZnJvbSBiZWluZyByZW1vdmVkIHNpbmNlIHRoZXJlIGlzXG4gICAgICAgICAgLy8gICAgICAgc3RpbGwgYSBjaGFuY2UgdGhleSB3aWxsIGJlIG1hdGNoZWQgdXAgbGF0ZXJcbiAgICAgICAgICByZW1vdmVOb2RlKGN1ckZyb21Ob2RlQ2hpbGQsIGZyb21FbCwgdHJ1ZSAvKiBza2lwIGtleWVkIG5vZGVzICovKTtcbiAgICAgICAgfVxuICAgICAgICBjdXJGcm9tTm9kZUNoaWxkID0gZnJvbU5leHRTaWJsaW5nO1xuICAgICAgfVxuICAgIH1cblxuICAgIGZ1bmN0aW9uIG1vcnBoRWwoZnJvbUVsLCB0b0VsLCBjaGlsZHJlbk9ubHkpIHtcbiAgICAgIHZhciB0b0VsS2V5ID0gZ2V0Tm9kZUtleSh0b0VsKTtcblxuICAgICAgaWYgKHRvRWxLZXkpIHtcbiAgICAgICAgLy8gSWYgYW4gZWxlbWVudCB3aXRoIGFuIElEIGlzIGJlaW5nIG1vcnBoZWQgdGhlbiBpdCB3aWxsIGJlIGluIHRoZSBmaW5hbFxuICAgICAgICAvLyBET00gc28gY2xlYXIgaXQgb3V0IG9mIHRoZSBzYXZlZCBlbGVtZW50cyBjb2xsZWN0aW9uXG4gICAgICAgIGRlbGV0ZSBmcm9tTm9kZXNMb29rdXBbdG9FbEtleV07XG4gICAgICB9XG5cbiAgICAgIGlmICghY2hpbGRyZW5Pbmx5KSB7XG4gICAgICAgIC8vIG9wdGlvbmFsXG4gICAgICAgIHZhciBiZWZvcmVVcGRhdGVSZXN1bHQgPSBvbkJlZm9yZUVsVXBkYXRlZChmcm9tRWwsIHRvRWwpO1xuICAgICAgICBpZiAoYmVmb3JlVXBkYXRlUmVzdWx0ID09PSBmYWxzZSkge1xuICAgICAgICAgIHJldHVybjtcbiAgICAgICAgfSBlbHNlIGlmIChiZWZvcmVVcGRhdGVSZXN1bHQgaW5zdGFuY2VvZiBIVE1MRWxlbWVudCkge1xuICAgICAgICAgIGZyb21FbCA9IGJlZm9yZVVwZGF0ZVJlc3VsdDtcbiAgICAgICAgICAvLyByZWluZGV4IHRoZSBuZXcgZnJvbUVsIGluIGNhc2UgaXQncyBub3QgaW4gdGhlIHNhbWVcbiAgICAgICAgICAvLyB0cmVlIGFzIHRoZSBvcmlnaW5hbCBmcm9tRWxcbiAgICAgICAgICAvLyAoUGhvZW5peCBMaXZlVmlldyBzb21ldGltZXMgcmV0dXJucyBhIGNsb25lZCB0cmVlLFxuICAgICAgICAgIC8vICBidXQga2V5ZWQgbG9va3VwcyB3b3VsZCBzdGlsbCBwb2ludCB0byB0aGUgb3JpZ2luYWwgdHJlZSlcbiAgICAgICAgICBpbmRleFRyZWUoZnJvbUVsKTtcbiAgICAgICAgfVxuXG4gICAgICAgIC8vIHVwZGF0ZSBhdHRyaWJ1dGVzIG9uIG9yaWdpbmFsIERPTSBlbGVtZW50IGZpcnN0XG4gICAgICAgIG1vcnBoQXR0cnMoZnJvbUVsLCB0b0VsKTtcbiAgICAgICAgLy8gb3B0aW9uYWxcbiAgICAgICAgb25FbFVwZGF0ZWQoZnJvbUVsKTtcblxuICAgICAgICBpZiAob25CZWZvcmVFbENoaWxkcmVuVXBkYXRlZChmcm9tRWwsIHRvRWwpID09PSBmYWxzZSkge1xuICAgICAgICAgIHJldHVybjtcbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBpZiAoZnJvbUVsLm5vZGVOYW1lICE9PSAnVEVYVEFSRUEnKSB7XG4gICAgICAgIG1vcnBoQ2hpbGRyZW4oZnJvbUVsLCB0b0VsKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHNwZWNpYWxFbEhhbmRsZXJzLlRFWFRBUkVBKGZyb21FbCwgdG9FbCk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgZnVuY3Rpb24gbW9ycGhDaGlsZHJlbihmcm9tRWwsIHRvRWwpIHtcbiAgICAgIHZhciBza2lwRnJvbSA9IHNraXBGcm9tQ2hpbGRyZW4oZnJvbUVsLCB0b0VsKTtcbiAgICAgIHZhciBjdXJUb05vZGVDaGlsZCA9IHRvRWwuZmlyc3RDaGlsZDtcbiAgICAgIHZhciBjdXJGcm9tTm9kZUNoaWxkID0gZnJvbUVsLmZpcnN0Q2hpbGQ7XG4gICAgICB2YXIgY3VyVG9Ob2RlS2V5O1xuICAgICAgdmFyIGN1ckZyb21Ob2RlS2V5O1xuXG4gICAgICB2YXIgZnJvbU5leHRTaWJsaW5nO1xuICAgICAgdmFyIHRvTmV4dFNpYmxpbmc7XG4gICAgICB2YXIgbWF0Y2hpbmdGcm9tRWw7XG5cbiAgICAgIC8vIHdhbGsgdGhlIGNoaWxkcmVuXG4gICAgICBvdXRlcjogd2hpbGUgKGN1clRvTm9kZUNoaWxkKSB7XG4gICAgICAgIHRvTmV4dFNpYmxpbmcgPSBjdXJUb05vZGVDaGlsZC5uZXh0U2libGluZztcbiAgICAgICAgY3VyVG9Ob2RlS2V5ID0gZ2V0Tm9kZUtleShjdXJUb05vZGVDaGlsZCk7XG5cbiAgICAgICAgLy8gd2FsayB0aGUgZnJvbU5vZGUgY2hpbGRyZW4gYWxsIHRoZSB3YXkgdGhyb3VnaFxuICAgICAgICB3aGlsZSAoIXNraXBGcm9tICYmIGN1ckZyb21Ob2RlQ2hpbGQpIHtcbiAgICAgICAgICBmcm9tTmV4dFNpYmxpbmcgPSBjdXJGcm9tTm9kZUNoaWxkLm5leHRTaWJsaW5nO1xuXG4gICAgICAgICAgaWYgKGN1clRvTm9kZUNoaWxkLmlzU2FtZU5vZGUgJiYgY3VyVG9Ob2RlQ2hpbGQuaXNTYW1lTm9kZShjdXJGcm9tTm9kZUNoaWxkKSkge1xuICAgICAgICAgICAgY3VyVG9Ob2RlQ2hpbGQgPSB0b05leHRTaWJsaW5nO1xuICAgICAgICAgICAgY3VyRnJvbU5vZGVDaGlsZCA9IGZyb21OZXh0U2libGluZztcbiAgICAgICAgICAgIGNvbnRpbnVlIG91dGVyO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGN1ckZyb21Ob2RlS2V5ID0gZ2V0Tm9kZUtleShjdXJGcm9tTm9kZUNoaWxkKTtcblxuICAgICAgICAgIHZhciBjdXJGcm9tTm9kZVR5cGUgPSBjdXJGcm9tTm9kZUNoaWxkLm5vZGVUeXBlO1xuXG4gICAgICAgICAgLy8gdGhpcyBtZWFucyBpZiB0aGUgY3VyRnJvbU5vZGVDaGlsZCBkb2VzbnQgaGF2ZSBhIG1hdGNoIHdpdGggdGhlIGN1clRvTm9kZUNoaWxkXG4gICAgICAgICAgdmFyIGlzQ29tcGF0aWJsZSA9IHVuZGVmaW5lZDtcblxuICAgICAgICAgIGlmIChjdXJGcm9tTm9kZVR5cGUgPT09IGN1clRvTm9kZUNoaWxkLm5vZGVUeXBlKSB7XG4gICAgICAgICAgICBpZiAoY3VyRnJvbU5vZGVUeXBlID09PSBFTEVNRU5UX05PREUpIHtcbiAgICAgICAgICAgICAgLy8gQm90aCBub2RlcyBiZWluZyBjb21wYXJlZCBhcmUgRWxlbWVudCBub2Rlc1xuXG4gICAgICAgICAgICAgIGlmIChjdXJUb05vZGVLZXkpIHtcbiAgICAgICAgICAgICAgICAvLyBUaGUgdGFyZ2V0IG5vZGUgaGFzIGEga2V5IHNvIHdlIHdhbnQgdG8gbWF0Y2ggaXQgdXAgd2l0aCB0aGUgY29ycmVjdCBlbGVtZW50XG4gICAgICAgICAgICAgICAgLy8gaW4gdGhlIG9yaWdpbmFsIERPTSB0cmVlXG4gICAgICAgICAgICAgICAgaWYgKGN1clRvTm9kZUtleSAhPT0gY3VyRnJvbU5vZGVLZXkpIHtcbiAgICAgICAgICAgICAgICAgIC8vIFRoZSBjdXJyZW50IGVsZW1lbnQgaW4gdGhlIG9yaWdpbmFsIERPTSB0cmVlIGRvZXMgbm90IGhhdmUgYSBtYXRjaGluZyBrZXkgc29cbiAgICAgICAgICAgICAgICAgIC8vIGxldCdzIGNoZWNrIG91ciBsb29rdXAgdG8gc2VlIGlmIHRoZXJlIGlzIGEgbWF0Y2hpbmcgZWxlbWVudCBpbiB0aGUgb3JpZ2luYWxcbiAgICAgICAgICAgICAgICAgIC8vIERPTSB0cmVlXG4gICAgICAgICAgICAgICAgICBpZiAoKG1hdGNoaW5nRnJvbUVsID0gZnJvbU5vZGVzTG9va3VwW2N1clRvTm9kZUtleV0pKSB7XG4gICAgICAgICAgICAgICAgICAgIGlmIChmcm9tTmV4dFNpYmxpbmcgPT09IG1hdGNoaW5nRnJvbUVsKSB7XG4gICAgICAgICAgICAgICAgICAgICAgLy8gU3BlY2lhbCBjYXNlIGZvciBzaW5nbGUgZWxlbWVudCByZW1vdmFscy4gVG8gYXZvaWQgcmVtb3ZpbmcgdGhlIG9yaWdpbmFsXG4gICAgICAgICAgICAgICAgICAgICAgLy8gRE9NIG5vZGUgb3V0IG9mIHRoZSB0cmVlIChzaW5jZSB0aGF0IGNhbiBicmVhayBDU1MgdHJhbnNpdGlvbnMsIGV0Yy4pLFxuICAgICAgICAgICAgICAgICAgICAgIC8vIHdlIHdpbGwgaW5zdGVhZCBkaXNjYXJkIHRoZSBjdXJyZW50IG5vZGUgYW5kIHdhaXQgdW50aWwgdGhlIG5leHRcbiAgICAgICAgICAgICAgICAgICAgICAvLyBpdGVyYXRpb24gdG8gcHJvcGVybHkgbWF0Y2ggdXAgdGhlIGtleWVkIHRhcmdldCBlbGVtZW50IHdpdGggaXRzIG1hdGNoaW5nXG4gICAgICAgICAgICAgICAgICAgICAgLy8gZWxlbWVudCBpbiB0aGUgb3JpZ2luYWwgdHJlZVxuICAgICAgICAgICAgICAgICAgICAgIGlzQ29tcGF0aWJsZSA9IGZhbHNlO1xuICAgICAgICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgICAgICAgIC8vIFdlIGZvdW5kIGEgbWF0Y2hpbmcga2V5ZWQgZWxlbWVudCBzb21ld2hlcmUgaW4gdGhlIG9yaWdpbmFsIERPTSB0cmVlLlxuICAgICAgICAgICAgICAgICAgICAgIC8vIExldCdzIG1vdmUgdGhlIG9yaWdpbmFsIERPTSBub2RlIGludG8gdGhlIGN1cnJlbnQgcG9zaXRpb24gYW5kIG1vcnBoXG4gICAgICAgICAgICAgICAgICAgICAgLy8gaXQuXG5cbiAgICAgICAgICAgICAgICAgICAgICAvLyBOT1RFOiBXZSB1c2UgaW5zZXJ0QmVmb3JlIGluc3RlYWQgb2YgcmVwbGFjZUNoaWxkIGJlY2F1c2Ugd2Ugd2FudCB0byBnbyB0aHJvdWdoXG4gICAgICAgICAgICAgICAgICAgICAgLy8gdGhlIGByZW1vdmVOb2RlKClgIGZ1bmN0aW9uIGZvciB0aGUgbm9kZSB0aGF0IGlzIGJlaW5nIGRpc2NhcmRlZCBzbyB0aGF0XG4gICAgICAgICAgICAgICAgICAgICAgLy8gYWxsIGxpZmVjeWNsZSBob29rcyBhcmUgY29ycmVjdGx5IGludm9rZWRcbiAgICAgICAgICAgICAgICAgICAgICBmcm9tRWwuaW5zZXJ0QmVmb3JlKG1hdGNoaW5nRnJvbUVsLCBjdXJGcm9tTm9kZUNoaWxkKTtcblxuICAgICAgICAgICAgICAgICAgICAgIC8vIGZyb21OZXh0U2libGluZyA9IGN1ckZyb21Ob2RlQ2hpbGQubmV4dFNpYmxpbmc7XG5cbiAgICAgICAgICAgICAgICAgICAgICBpZiAoY3VyRnJvbU5vZGVLZXkpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIC8vIFNpbmNlIHRoZSBub2RlIGlzIGtleWVkIGl0IG1pZ2h0IGJlIG1hdGNoZWQgdXAgbGF0ZXIgc28gd2UgZGVmZXJcbiAgICAgICAgICAgICAgICAgICAgICAgIC8vIHRoZSBhY3R1YWwgcmVtb3ZhbCB0byBsYXRlclxuICAgICAgICAgICAgICAgICAgICAgICAgYWRkS2V5ZWRSZW1vdmFsKGN1ckZyb21Ob2RlS2V5KTtcbiAgICAgICAgICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgICAgICAgICAgLy8gTk9URTogd2Ugc2tpcCBuZXN0ZWQga2V5ZWQgbm9kZXMgZnJvbSBiZWluZyByZW1vdmVkIHNpbmNlIHRoZXJlIGlzXG4gICAgICAgICAgICAgICAgICAgICAgICAvLyAgICAgICBzdGlsbCBhIGNoYW5jZSB0aGV5IHdpbGwgYmUgbWF0Y2hlZCB1cCBsYXRlclxuICAgICAgICAgICAgICAgICAgICAgICAgcmVtb3ZlTm9kZShjdXJGcm9tTm9kZUNoaWxkLCBmcm9tRWwsIHRydWUgLyogc2tpcCBrZXllZCBub2RlcyAqLyk7XG4gICAgICAgICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgICAgICAgY3VyRnJvbU5vZGVDaGlsZCA9IG1hdGNoaW5nRnJvbUVsO1xuICAgICAgICAgICAgICAgICAgICAgIGN1ckZyb21Ob2RlS2V5ID0gZ2V0Tm9kZUtleShjdXJGcm9tTm9kZUNoaWxkKTtcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgLy8gVGhlIG5vZGVzIGFyZSBub3QgY29tcGF0aWJsZSBzaW5jZSB0aGUgXCJ0b1wiIG5vZGUgaGFzIGEga2V5IGFuZCB0aGVyZVxuICAgICAgICAgICAgICAgICAgICAvLyBpcyBubyBtYXRjaGluZyBrZXllZCBub2RlIGluIHRoZSBzb3VyY2UgdHJlZVxuICAgICAgICAgICAgICAgICAgICBpc0NvbXBhdGlibGUgPSBmYWxzZTtcbiAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIH0gZWxzZSBpZiAoY3VyRnJvbU5vZGVLZXkpIHtcbiAgICAgICAgICAgICAgICAvLyBUaGUgb3JpZ2luYWwgaGFzIGEga2V5XG4gICAgICAgICAgICAgICAgaXNDb21wYXRpYmxlID0gZmFsc2U7XG4gICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICBpc0NvbXBhdGlibGUgPSBpc0NvbXBhdGlibGUgIT09IGZhbHNlICYmIGNvbXBhcmVOb2RlTmFtZXMoY3VyRnJvbU5vZGVDaGlsZCwgY3VyVG9Ob2RlQ2hpbGQpO1xuICAgICAgICAgICAgICBpZiAoaXNDb21wYXRpYmxlKSB7XG4gICAgICAgICAgICAgICAgLy8gV2UgZm91bmQgY29tcGF0aWJsZSBET00gZWxlbWVudHMgc28gdHJhbnNmb3JtXG4gICAgICAgICAgICAgICAgLy8gdGhlIGN1cnJlbnQgXCJmcm9tXCIgbm9kZSB0byBtYXRjaCB0aGUgY3VycmVudFxuICAgICAgICAgICAgICAgIC8vIHRhcmdldCBET00gbm9kZS5cbiAgICAgICAgICAgICAgICAvLyBNT1JQSFxuICAgICAgICAgICAgICAgIG1vcnBoRWwoY3VyRnJvbU5vZGVDaGlsZCwgY3VyVG9Ob2RlQ2hpbGQpO1xuICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIH0gZWxzZSBpZiAoY3VyRnJvbU5vZGVUeXBlID09PSBURVhUX05PREUgfHwgY3VyRnJvbU5vZGVUeXBlID09IENPTU1FTlRfTk9ERSkge1xuICAgICAgICAgICAgICAvLyBCb3RoIG5vZGVzIGJlaW5nIGNvbXBhcmVkIGFyZSBUZXh0IG9yIENvbW1lbnQgbm9kZXNcbiAgICAgICAgICAgICAgaXNDb21wYXRpYmxlID0gdHJ1ZTtcbiAgICAgICAgICAgICAgLy8gU2ltcGx5IHVwZGF0ZSBub2RlVmFsdWUgb24gdGhlIG9yaWdpbmFsIG5vZGUgdG9cbiAgICAgICAgICAgICAgLy8gY2hhbmdlIHRoZSB0ZXh0IHZhbHVlXG4gICAgICAgICAgICAgIGlmIChjdXJGcm9tTm9kZUNoaWxkLm5vZGVWYWx1ZSAhPT0gY3VyVG9Ob2RlQ2hpbGQubm9kZVZhbHVlKSB7XG4gICAgICAgICAgICAgICAgY3VyRnJvbU5vZGVDaGlsZC5ub2RlVmFsdWUgPSBjdXJUb05vZGVDaGlsZC5ub2RlVmFsdWU7XG4gICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChpc0NvbXBhdGlibGUpIHtcbiAgICAgICAgICAgIC8vIEFkdmFuY2UgYm90aCB0aGUgXCJ0b1wiIGNoaWxkIGFuZCB0aGUgXCJmcm9tXCIgY2hpbGQgc2luY2Ugd2UgZm91bmQgYSBtYXRjaFxuICAgICAgICAgICAgLy8gTm90aGluZyBlbHNlIHRvIGRvIGFzIHdlIGFscmVhZHkgcmVjdXJzaXZlbHkgY2FsbGVkIG1vcnBoQ2hpbGRyZW4gYWJvdmVcbiAgICAgICAgICAgIGN1clRvTm9kZUNoaWxkID0gdG9OZXh0U2libGluZztcbiAgICAgICAgICAgIGN1ckZyb21Ob2RlQ2hpbGQgPSBmcm9tTmV4dFNpYmxpbmc7XG4gICAgICAgICAgICBjb250aW51ZSBvdXRlcjtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICAvLyBObyBjb21wYXRpYmxlIG1hdGNoIHNvIHJlbW92ZSB0aGUgb2xkIG5vZGUgZnJvbSB0aGUgRE9NIGFuZCBjb250aW51ZSB0cnlpbmcgdG8gZmluZCBhXG4gICAgICAgICAgLy8gbWF0Y2ggaW4gdGhlIG9yaWdpbmFsIERPTS4gSG93ZXZlciwgd2Ugb25seSBkbyB0aGlzIGlmIHRoZSBmcm9tIG5vZGUgaXMgbm90IGtleWVkXG4gICAgICAgICAgLy8gc2luY2UgaXQgaXMgcG9zc2libGUgdGhhdCBhIGtleWVkIG5vZGUgbWlnaHQgbWF0Y2ggdXAgd2l0aCBhIG5vZGUgc29tZXdoZXJlIGVsc2UgaW4gdGhlXG4gICAgICAgICAgLy8gdGFyZ2V0IHRyZWUgYW5kIHdlIGRvbid0IHdhbnQgdG8gZGlzY2FyZCBpdCBqdXN0IHlldCBzaW5jZSBpdCBzdGlsbCBtaWdodCBmaW5kIGFcbiAgICAgICAgICAvLyBob21lIGluIHRoZSBmaW5hbCBET00gdHJlZS4gQWZ0ZXIgZXZlcnl0aGluZyBpcyBkb25lIHdlIHdpbGwgcmVtb3ZlIGFueSBrZXllZCBub2Rlc1xuICAgICAgICAgIC8vIHRoYXQgZGlkbid0IGZpbmQgYSBob21lXG4gICAgICAgICAgaWYgKGN1ckZyb21Ob2RlS2V5KSB7XG4gICAgICAgICAgICAvLyBTaW5jZSB0aGUgbm9kZSBpcyBrZXllZCBpdCBtaWdodCBiZSBtYXRjaGVkIHVwIGxhdGVyIHNvIHdlIGRlZmVyXG4gICAgICAgICAgICAvLyB0aGUgYWN0dWFsIHJlbW92YWwgdG8gbGF0ZXJcbiAgICAgICAgICAgIGFkZEtleWVkUmVtb3ZhbChjdXJGcm9tTm9kZUtleSk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIC8vIE5PVEU6IHdlIHNraXAgbmVzdGVkIGtleWVkIG5vZGVzIGZyb20gYmVpbmcgcmVtb3ZlZCBzaW5jZSB0aGVyZSBpc1xuICAgICAgICAgICAgLy8gICAgICAgc3RpbGwgYSBjaGFuY2UgdGhleSB3aWxsIGJlIG1hdGNoZWQgdXAgbGF0ZXJcbiAgICAgICAgICAgIHJlbW92ZU5vZGUoY3VyRnJvbU5vZGVDaGlsZCwgZnJvbUVsLCB0cnVlIC8qIHNraXAga2V5ZWQgbm9kZXMgKi8pO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGN1ckZyb21Ob2RlQ2hpbGQgPSBmcm9tTmV4dFNpYmxpbmc7XG4gICAgICAgIH0gLy8gRU5EOiB3aGlsZShjdXJGcm9tTm9kZUNoaWxkKSB7fVxuXG4gICAgICAgIC8vIElmIHdlIGdvdCB0aGlzIGZhciB0aGVuIHdlIGRpZCBub3QgZmluZCBhIGNhbmRpZGF0ZSBtYXRjaCBmb3JcbiAgICAgICAgLy8gb3VyIFwidG8gbm9kZVwiIGFuZCB3ZSBleGhhdXN0ZWQgYWxsIG9mIHRoZSBjaGlsZHJlbiBcImZyb21cIlxuICAgICAgICAvLyBub2Rlcy4gVGhlcmVmb3JlLCB3ZSB3aWxsIGp1c3QgYXBwZW5kIHRoZSBjdXJyZW50IFwidG9cIiBub2RlXG4gICAgICAgIC8vIHRvIHRoZSBlbmRcbiAgICAgICAgaWYgKGN1clRvTm9kZUtleSAmJiAobWF0Y2hpbmdGcm9tRWwgPSBmcm9tTm9kZXNMb29rdXBbY3VyVG9Ob2RlS2V5XSkgJiYgY29tcGFyZU5vZGVOYW1lcyhtYXRjaGluZ0Zyb21FbCwgY3VyVG9Ob2RlQ2hpbGQpKSB7XG4gICAgICAgICAgLy8gTU9SUEhcbiAgICAgICAgICBpZighc2tpcEZyb20peyBhZGRDaGlsZChmcm9tRWwsIG1hdGNoaW5nRnJvbUVsKTsgfVxuICAgICAgICAgIG1vcnBoRWwobWF0Y2hpbmdGcm9tRWwsIGN1clRvTm9kZUNoaWxkKTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICB2YXIgb25CZWZvcmVOb2RlQWRkZWRSZXN1bHQgPSBvbkJlZm9yZU5vZGVBZGRlZChjdXJUb05vZGVDaGlsZCk7XG4gICAgICAgICAgaWYgKG9uQmVmb3JlTm9kZUFkZGVkUmVzdWx0ICE9PSBmYWxzZSkge1xuICAgICAgICAgICAgaWYgKG9uQmVmb3JlTm9kZUFkZGVkUmVzdWx0KSB7XG4gICAgICAgICAgICAgIGN1clRvTm9kZUNoaWxkID0gb25CZWZvcmVOb2RlQWRkZWRSZXN1bHQ7XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChjdXJUb05vZGVDaGlsZC5hY3R1YWxpemUpIHtcbiAgICAgICAgICAgICAgY3VyVG9Ob2RlQ2hpbGQgPSBjdXJUb05vZGVDaGlsZC5hY3R1YWxpemUoZnJvbUVsLm93bmVyRG9jdW1lbnQgfHwgZG9jKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGFkZENoaWxkKGZyb21FbCwgY3VyVG9Ob2RlQ2hpbGQpO1xuICAgICAgICAgICAgaGFuZGxlTm9kZUFkZGVkKGN1clRvTm9kZUNoaWxkKTtcbiAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBjdXJUb05vZGVDaGlsZCA9IHRvTmV4dFNpYmxpbmc7XG4gICAgICAgIGN1ckZyb21Ob2RlQ2hpbGQgPSBmcm9tTmV4dFNpYmxpbmc7XG4gICAgICB9XG5cbiAgICAgIGNsZWFudXBGcm9tRWwoZnJvbUVsLCBjdXJGcm9tTm9kZUNoaWxkLCBjdXJGcm9tTm9kZUtleSk7XG5cbiAgICAgIHZhciBzcGVjaWFsRWxIYW5kbGVyID0gc3BlY2lhbEVsSGFuZGxlcnNbZnJvbUVsLm5vZGVOYW1lXTtcbiAgICAgIGlmIChzcGVjaWFsRWxIYW5kbGVyKSB7XG4gICAgICAgIHNwZWNpYWxFbEhhbmRsZXIoZnJvbUVsLCB0b0VsKTtcbiAgICAgIH1cbiAgICB9IC8vIEVORDogbW9ycGhDaGlsZHJlbiguLi4pXG5cbiAgICB2YXIgbW9ycGhlZE5vZGUgPSBmcm9tTm9kZTtcbiAgICB2YXIgbW9ycGhlZE5vZGVUeXBlID0gbW9ycGhlZE5vZGUubm9kZVR5cGU7XG4gICAgdmFyIHRvTm9kZVR5cGUgPSB0b05vZGUubm9kZVR5cGU7XG5cbiAgICBpZiAoIWNoaWxkcmVuT25seSkge1xuICAgICAgLy8gSGFuZGxlIHRoZSBjYXNlIHdoZXJlIHdlIGFyZSBnaXZlbiB0d28gRE9NIG5vZGVzIHRoYXQgYXJlIG5vdFxuICAgICAgLy8gY29tcGF0aWJsZSAoZS5nLiA8ZGl2PiAtLT4gPHNwYW4+IG9yIDxkaXY+IC0tPiBURVhUKVxuICAgICAgaWYgKG1vcnBoZWROb2RlVHlwZSA9PT0gRUxFTUVOVF9OT0RFKSB7XG4gICAgICAgIGlmICh0b05vZGVUeXBlID09PSBFTEVNRU5UX05PREUpIHtcbiAgICAgICAgICBpZiAoIWNvbXBhcmVOb2RlTmFtZXMoZnJvbU5vZGUsIHRvTm9kZSkpIHtcbiAgICAgICAgICAgIG9uTm9kZURpc2NhcmRlZChmcm9tTm9kZSk7XG4gICAgICAgICAgICBtb3JwaGVkTm9kZSA9IG1vdmVDaGlsZHJlbihmcm9tTm9kZSwgY3JlYXRlRWxlbWVudE5TKHRvTm9kZS5ub2RlTmFtZSwgdG9Ob2RlLm5hbWVzcGFjZVVSSSkpO1xuICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAvLyBHb2luZyBmcm9tIGFuIGVsZW1lbnQgbm9kZSB0byBhIHRleHQgbm9kZVxuICAgICAgICAgIG1vcnBoZWROb2RlID0gdG9Ob2RlO1xuICAgICAgICB9XG4gICAgICB9IGVsc2UgaWYgKG1vcnBoZWROb2RlVHlwZSA9PT0gVEVYVF9OT0RFIHx8IG1vcnBoZWROb2RlVHlwZSA9PT0gQ09NTUVOVF9OT0RFKSB7IC8vIFRleHQgb3IgY29tbWVudCBub2RlXG4gICAgICAgIGlmICh0b05vZGVUeXBlID09PSBtb3JwaGVkTm9kZVR5cGUpIHtcbiAgICAgICAgICBpZiAobW9ycGhlZE5vZGUubm9kZVZhbHVlICE9PSB0b05vZGUubm9kZVZhbHVlKSB7XG4gICAgICAgICAgICBtb3JwaGVkTm9kZS5ub2RlVmFsdWUgPSB0b05vZGUubm9kZVZhbHVlO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIHJldHVybiBtb3JwaGVkTm9kZTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAvLyBUZXh0IG5vZGUgdG8gc29tZXRoaW5nIGVsc2VcbiAgICAgICAgICBtb3JwaGVkTm9kZSA9IHRvTm9kZTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChtb3JwaGVkTm9kZSA9PT0gdG9Ob2RlKSB7XG4gICAgICAvLyBUaGUgXCJ0byBub2RlXCIgd2FzIG5vdCBjb21wYXRpYmxlIHdpdGggdGhlIFwiZnJvbSBub2RlXCIgc28gd2UgaGFkIHRvXG4gICAgICAvLyB0b3NzIG91dCB0aGUgXCJmcm9tIG5vZGVcIiBhbmQgdXNlIHRoZSBcInRvIG5vZGVcIlxuICAgICAgb25Ob2RlRGlzY2FyZGVkKGZyb21Ob2RlKTtcbiAgICB9IGVsc2Uge1xuICAgICAgaWYgKHRvTm9kZS5pc1NhbWVOb2RlICYmIHRvTm9kZS5pc1NhbWVOb2RlKG1vcnBoZWROb2RlKSkge1xuICAgICAgICByZXR1cm47XG4gICAgICB9XG5cbiAgICAgIG1vcnBoRWwobW9ycGhlZE5vZGUsIHRvTm9kZSwgY2hpbGRyZW5Pbmx5KTtcblxuICAgICAgLy8gV2Ugbm93IG5lZWQgdG8gbG9vcCBvdmVyIGFueSBrZXllZCBub2RlcyB0aGF0IG1pZ2h0IG5lZWQgdG8gYmVcbiAgICAgIC8vIHJlbW92ZWQuIFdlIG9ubHkgZG8gdGhlIHJlbW92YWwgaWYgd2Uga25vdyB0aGF0IHRoZSBrZXllZCBub2RlXG4gICAgICAvLyBuZXZlciBmb3VuZCBhIG1hdGNoLiBXaGVuIGEga2V5ZWQgbm9kZSBpcyBtYXRjaGVkIHVwIHdlIHJlbW92ZVxuICAgICAgLy8gaXQgb3V0IG9mIGZyb21Ob2Rlc0xvb2t1cCBhbmQgd2UgdXNlIGZyb21Ob2Rlc0xvb2t1cCB0byBkZXRlcm1pbmVcbiAgICAgIC8vIGlmIGEga2V5ZWQgbm9kZSBoYXMgYmVlbiBtYXRjaGVkIHVwIG9yIG5vdFxuICAgICAgaWYgKGtleWVkUmVtb3ZhbExpc3QpIHtcbiAgICAgICAgZm9yICh2YXIgaT0wLCBsZW49a2V5ZWRSZW1vdmFsTGlzdC5sZW5ndGg7IGk8bGVuOyBpKyspIHtcbiAgICAgICAgICB2YXIgZWxUb1JlbW92ZSA9IGZyb21Ob2Rlc0xvb2t1cFtrZXllZFJlbW92YWxMaXN0W2ldXTtcbiAgICAgICAgICBpZiAoZWxUb1JlbW92ZSkge1xuICAgICAgICAgICAgcmVtb3ZlTm9kZShlbFRvUmVtb3ZlLCBlbFRvUmVtb3ZlLnBhcmVudE5vZGUsIGZhbHNlKTtcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoIWNoaWxkcmVuT25seSAmJiBtb3JwaGVkTm9kZSAhPT0gZnJvbU5vZGUgJiYgZnJvbU5vZGUucGFyZW50Tm9kZSkge1xuICAgICAgaWYgKG1vcnBoZWROb2RlLmFjdHVhbGl6ZSkge1xuICAgICAgICBtb3JwaGVkTm9kZSA9IG1vcnBoZWROb2RlLmFjdHVhbGl6ZShmcm9tTm9kZS5vd25lckRvY3VtZW50IHx8IGRvYyk7XG4gICAgICB9XG4gICAgICAvLyBJZiB3ZSBoYWQgdG8gc3dhcCBvdXQgdGhlIGZyb20gbm9kZSB3aXRoIGEgbmV3IG5vZGUgYmVjYXVzZSB0aGUgb2xkXG4gICAgICAvLyBub2RlIHdhcyBub3QgY29tcGF0aWJsZSB3aXRoIHRoZSB0YXJnZXQgbm9kZSB0aGVuIHdlIG5lZWQgdG9cbiAgICAgIC8vIHJlcGxhY2UgdGhlIG9sZCBET00gbm9kZSBpbiB0aGUgb3JpZ2luYWwgRE9NIHRyZWUuIFRoaXMgaXMgb25seVxuICAgICAgLy8gcG9zc2libGUgaWYgdGhlIG9yaWdpbmFsIERPTSBub2RlIHdhcyBwYXJ0IG9mIGEgRE9NIHRyZWUgd2hpY2hcbiAgICAgIC8vIHdlIGtub3cgaXMgdGhlIGNhc2UgaWYgaXQgaGFzIGEgcGFyZW50IG5vZGUuXG4gICAgICBmcm9tTm9kZS5wYXJlbnROb2RlLnJlcGxhY2VDaGlsZChtb3JwaGVkTm9kZSwgZnJvbU5vZGUpO1xuICAgIH1cblxuICAgIHJldHVybiBtb3JwaGVkTm9kZTtcbiAgfTtcbn1cblxudmFyIG1vcnBoZG9tID0gbW9ycGhkb21GYWN0b3J5KG1vcnBoQXR0cnMpO1xuXG5leHBvcnQgZGVmYXVsdCBtb3JwaGRvbTtcbiIsICJpbXBvcnQgXCIuL2NvbXBvbmVudHNcIjtcbmltcG9ydCB7IGluaXRFdmVudE1hbmFnZXIgfSBmcm9tIFwiLi9ldmVudHNcIjtcbmltcG9ydCB7IGluaXRUcmFuc3BvcnQsIFRyYW5zcG9ydENvbmZpZyB9IGZyb20gXCIuL3RyYW5zcG9ydFwiO1xuaW1wb3J0IHsgSW5pdERhdGEsIE91dHB1dEV2ZW50LCBDdXN0b21FdmVudEhhbmRsZXIgfSBmcm9tIFwiLi90eXBlc1wiO1xuaW1wb3J0IG1vcnBoZG9tIGZyb20gXCJtb3JwaGRvbVwiO1xuXG5jb25zdCBkZWZhdWx0VGFyZ2V0SWQgPSBcInJvb3RcIjtcbmNvbnN0IG91dHB1dEN1c3RvbUV2ZW50SGFuZGxlcnMgPSBuZXcgTWFwPHN0cmluZywgU2V0PEN1c3RvbUV2ZW50SGFuZGxlcj4+KCk7XG5sZXQgb3JpZ2luVXJsOiBzdHJpbmcgfCB1bmRlZmluZWQ7XG5cbmNvbnN0IHRyYW5zcG9ydENvbmZpZzogVHJhbnNwb3J0Q29uZmlnID0ge1xuICAgIHN0YXRlVG9rZW46IFwiXCIsXG4gICAgb25VcGRhdGU6IChodG1sUGFydHM6IHN0cmluZ1tdLCBldmVudHM6IE91dHB1dEV2ZW50W10pID0+IHtcbiAgICAgICAgZm9yIChjb25zdCBodG1sUGFydCBvZiBodG1sUGFydHMpIHtcbiAgICAgICAgICAgIGFwcGx5SFRNTChodG1sUGFydCk7XG4gICAgICAgIH1cbiAgICAgICAgb25PdXRwdXRFdmVudHMoZXZlbnRzKTtcbiAgICB9LFxuICAgIHBvcFBlbmRpbmdFdmVudHM6ICgpID0+IGV2ZW50TWFuYWdlci5wb3BQZW5kaW5nRXZlbnRzKClcbn07XG5cbmNvbnN0IHRyYW5zcG9ydCA9IGluaXRUcmFuc3BvcnQodHJhbnNwb3J0Q29uZmlnKTtcbmNvbnN0IGV2ZW50TWFuYWdlciA9IGluaXRFdmVudE1hbmFnZXIodHJhbnNwb3J0LnVwZGF0ZSk7XG5cbmNvbnN0IGFwcGx5SFRNTCA9IChodG1sPzogc3RyaW5nKSA9PiB7XG4gICAgbGV0IHRhcmdldDogRWxlbWVudDtcblxuICAgIGlmIChodG1sID09PSB1bmRlZmluZWQpIHtcbiAgICAgICAgY29uc3QgdHRhcmdldCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKGRlZmF1bHRUYXJnZXRJZCk7XG4gICAgICAgIGlmICh0dGFyZ2V0ID09PSBudWxsKSB7XG4gICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoXCJVcGRhdGUgdGFyZ2V0IG5vdCBmb3VuZCFcIik7XG4gICAgICAgIH1cbiAgICAgICAgdGFyZ2V0ID0gdHRhcmdldDtcbiAgICB9IGVsc2Uge1xuICAgICAgICBjb25zdCB0ZW1wID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudChcImRpdlwiKTtcbiAgICAgICAgdGVtcC5pbm5lckhUTUwgPSBodG1sO1xuXG4gICAgICAgIGNvbnN0IHVwZGF0ZVJvb3QgPSB0ZW1wLmNoaWxkcmVuLml0ZW0oMCk7XG4gICAgICAgIGlmIChcbiAgICAgICAgICAgIHVwZGF0ZVJvb3QgPT09IG51bGwgfHxcbiAgICAgICAgICAgIHVwZGF0ZVJvb3QudGFnTmFtZSAhPT0gXCJyeHh4dC1tZXRhXCIudG9VcHBlckNhc2UoKVxuICAgICAgICApIHtcbiAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcihcIkludmFsaWQgdXBkYXRlIHJvb3QhXCIpO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgdHRhcmdldCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKHVwZGF0ZVJvb3QuaWQpO1xuICAgICAgICBpZiAodHRhcmdldCA9PT0gbnVsbCkge1xuICAgICAgICAgICAgdGhyb3cgbmV3IEVycm9yKFwiVXBkYXRlIHRhcmdldCBub3QgZm91bmQhXCIpO1xuICAgICAgICB9XG5cbiAgICAgICAgdGFyZ2V0ID0gdHRhcmdldDtcbiAgICAgICAgbW9ycGhkb20odGFyZ2V0LCB1cGRhdGVSb290KTtcbiAgICB9XG5cbiAgICBmb3IgKGNvbnN0IGVsZW1lbnQgb2YgdGFyZ2V0LmdldEVsZW1lbnRzQnlUYWdOYW1lKFwiKlwiKSkge1xuICAgICAgICBldmVudE1hbmFnZXIub25FbGVtZW50VXBkYXRlZChlbGVtZW50KTtcbiAgICB9XG59O1xuXG5jb25zdCBvdXRwdXRFdmVudEhhbmRsZXJzOiB7IFtLIGluIE91dHB1dEV2ZW50WydldmVudCddXTogKGV2OiBFeHRyYWN0PE91dHB1dEV2ZW50LCB7IGV2ZW50OiBLIH0+KSA9PiB2b2lkOyB9ID0ge1xuICAgIGN1c3RvbTogZXZlbnQgPT4ge1xuICAgICAgICBmb3IgKGNvbnN0IGhhbmRsZXIgb2Ygb3V0cHV0Q3VzdG9tRXZlbnRIYW5kbGVycy5nZXQoZXZlbnQubmFtZSkgPz8gW10pIHtcbiAgICAgICAgICAgIHRyeSB7XG4gICAgICAgICAgICAgICAgaGFuZGxlcihldmVudC5kYXRhKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGNhdGNoIChlKSB7XG4gICAgICAgICAgICAgICAgY29uc29sZS5lcnJvcihlKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIH0sXG4gICAgbmF2aWdhdGU6IGV2ZW50ID0+IHtcbiAgICAgICAgY29uc3QgdGFyZ2V0VXJsID0gbmV3IFVSTChldmVudC5sb2NhdGlvbiwgbG9jYXRpb24uaHJlZik7XG4gICAgICAgIGlmIChvcmlnaW5VcmwgPT09IHVuZGVmaW5lZCB8fCBvcmlnaW5VcmwgIT09IHRhcmdldFVybC5vcmlnaW4pIHtcbiAgICAgICAgICAgIGxvY2F0aW9uLmFzc2lnbih0YXJnZXRVcmwpO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgd2luZG93Lmhpc3RvcnkucHVzaFN0YXRlKHt9LCBcIlwiLCBldmVudC5sb2NhdGlvbik7XG4gICAgICAgICAgICBpZiAoZXZlbnQucmVxdWlyZXNfcmVmcmVzaCkge1xuICAgICAgICAgICAgICAgIHRyYW5zcG9ydC51cGRhdGUoKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIH0sXG4gICAgXCJ1c2Utd2Vic29ja2V0XCI6IGV2ZW50ID0+IHtcbiAgICAgICAgaWYgKGV2ZW50LndlYnNvY2tldCkge1xuICAgICAgICAgICAgdHJhbnNwb3J0LnVzZVdlYlNvY2tldCgpO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgdHJhbnNwb3J0LnVzZUhUVFAoKTtcbiAgICAgICAgfVxuICAgIH0sXG4gICAgXCJzZXQtY29va2llXCI6IGV2ZW50ID0+IHtcbiAgICAgICAgY29uc3QgcGFydHM6IHN0cmluZ1tdID0gW2Ake2V2ZW50Lm5hbWV9PSR7ZXZlbnQudmFsdWUgPz8gXCJcIn1gXTtcbiAgICAgICAgaWYgKHR5cGVvZiBldmVudC5wYXRoID09PSBcInN0cmluZ1wiKSBwYXJ0cy5wdXNoKGBwYXRoPSR7ZXZlbnQucGF0aH1gKTtcbiAgICAgICAgaWYgKHR5cGVvZiBldmVudC5leHBpcmVzID09PSBcInN0cmluZ1wiKSBwYXJ0cy5wdXNoKGBleHBpcmVzPSR7bmV3IERhdGUoZXZlbnQuZXhwaXJlcykudG9VVENTdHJpbmcoKX1gKTtcbiAgICAgICAgaWYgKHR5cGVvZiBldmVudC5tYXhfYWdlID09PSBcIm51bWJlclwiKSBwYXJ0cy5wdXNoKGBtYXgtYWdlPSR7ZXZlbnQubWF4X2FnZX1gKTtcbiAgICAgICAgaWYgKHR5cGVvZiBldmVudC5kb21haW4gPT09IFwic3RyaW5nXCIpIHBhcnRzLnB1c2goYGRvbWFpbj0ke2V2ZW50LmRvbWFpbn1gKTtcbiAgICAgICAgaWYgKGV2ZW50LnNlY3VyZSkgcGFydHMucHVzaChgc2VjdXJlYCk7XG4gICAgICAgIGlmIChldmVudC5odHRwX29ubHkpIHBhcnRzLnB1c2goYGh0dHBvbmx5YCk7XG5cbiAgICAgICAgZG9jdW1lbnQuY29va2llID0gcGFydHMuam9pbihcIjtcIik7XG4gICAgfVxufTtcblxuY29uc3Qgb25PdXRwdXRFdmVudHMgPSAoZXZlbnRzOiBPdXRwdXRFdmVudFtdKSA9PiBldmVudHMuZm9yRWFjaChldmVudCA9PiBvdXRwdXRFdmVudEhhbmRsZXJzW2V2ZW50LmV2ZW50XShldmVudCBhcyBhbnkpKTsgLy8gdHlwZXNjcmlwdCBkb2VzbnQgaGFuZGxlIHRoaXMgd2VsbFxuXG5jb25zdCByeHh4dCA9IHtcbiAgICBvbjogKG5hbWU6IHN0cmluZywgaGFuZGxlcjogQ3VzdG9tRXZlbnRIYW5kbGVyKSA9PiB7XG4gICAgICAgIGNvbnN0IGhhbmRsZXJzID0gb3V0cHV0Q3VzdG9tRXZlbnRIYW5kbGVycy5nZXQobmFtZSkgPz8gbmV3IFNldCgpO1xuICAgICAgICBvdXRwdXRDdXN0b21FdmVudEhhbmRsZXJzLnNldChuYW1lLCBoYW5kbGVycylcbiAgICAgICAgaGFuZGxlcnMuYWRkKGhhbmRsZXIpXG4gICAgfSxcbiAgICBvZmY6IChuYW1lOiBzdHJpbmcsIGhhbmRsZXI6IEN1c3RvbUV2ZW50SGFuZGxlcikgPT4ge1xuICAgICAgICBjb25zdCBoYW5kbGVycyA9IG91dHB1dEN1c3RvbUV2ZW50SGFuZGxlcnMuZ2V0KG5hbWUpID8/IG5ldyBTZXQoKTtcbiAgICAgICAgcmV0dXJuIGhhbmRsZXJzLmRlbGV0ZShoYW5kbGVyKTtcbiAgICB9LFxuICAgIG5hdmlnYXRlOiAodXJsOiBzdHJpbmcgfCBVUkwpID0+IHtcbiAgICAgICAgb25PdXRwdXRFdmVudHMoW3sgZXZlbnQ6IFwibmF2aWdhdGVcIiwgbG9jYXRpb246IG5ldyBVUkwodXJsLCBsb2NhdGlvbi5ocmVmKS5ocmVmLCByZXF1aXJlc19yZWZyZXNoOiB0cnVlIH1dKTtcbiAgICB9LFxuICAgIGluaXQ6IChkYXRhOiBJbml0RGF0YSkgPT4ge1xuICAgICAgICBvcmlnaW5VcmwgPSAobmV3IFVSTChsb2NhdGlvbi5ocmVmKSkub3JpZ2luO1xuXG4gICAgICAgIHdpbmRvdy5hZGRFdmVudExpc3RlbmVyKFwicG9wc3RhdGVcIiwgdHJhbnNwb3J0LnVwZGF0ZSk7XG4gICAgICAgIHRyYW5zcG9ydENvbmZpZy5zdGF0ZVRva2VuID0gZGF0YS5zdGF0ZV90b2tlbjtcbiAgICAgICAgdHJhbnNwb3J0Q29uZmlnLmVuYWJsZVdlYlNvY2tldFN0YXRlVXBkYXRlcyA9IGRhdGEuZW5hYmxlX3dlYl9zb2NrZXRfc3RhdGVfdXBkYXRlcztcbiAgICAgICAgdHJhbnNwb3J0Q29uZmlnLmRpc2FibGVIVFRQUmV0cnkgPSBkYXRhLmRpc2FibGVfaHR0cF91cGRhdGVfcmV0cnk7XG4gICAgICAgIG9uT3V0cHV0RXZlbnRzKGRhdGEuZXZlbnRzKTtcbiAgICAgICAgYXBwbHlIVE1MKCk7XG4gICAgfSxcbn07XG5cbih3aW5kb3cgYXMgYW55KS5yeHh4dCA9IHJ4eHh0O1xuY29uc3QgaW5pdERhdGFFbGVtZW50ID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoXCJyeHh4dC1pbml0LWRhdGFcIik7XG5pZiAoaW5pdERhdGFFbGVtZW50ICE9IG51bGwgJiYgaW5pdERhdGFFbGVtZW50LnRleHRDb250ZW50ICE9PSBudWxsKSB7XG4gICAgcnh4eHQuaW5pdChKU09OLnBhcnNlKGluaXREYXRhRWxlbWVudC50ZXh0Q29udGVudCkpO1xufVxuZWxzZSB7XG4gICAgY29uc29sZS53YXJuKFwiZmFpbGVkIHRvIGluaXRpYWxpemUgcnh4eHQuIGluaXQgZGF0YSBub3QgZm91bmQuXCIpXG59XG4iXSwKICAibWFwcGluZ3MiOiAiOzs7Ozs7Ozs7Ozs7Ozs7Ozs7OztBQUFBLE1BQU0sc0JBQXNCO0FBRzVCLE1BQWUsbUJBQWYsY0FBd0MsWUFBWTtBQUFBLElBQXBEO0FBQUE7QUFDSSwwQkFBVSxZQUEwQixDQUFDLFVBQWlCLEtBQUssY0FBYyxJQUFJLFlBQVksUUFBUSxFQUFFLFFBQVEsTUFBTSxDQUFDLENBQUM7QUFDbkgsMEJBQVUsbUJBQWtCLG9CQUFJLElBQTJCO0FBQUE7QUFBQSxJQUUzRCxXQUFrQixxQkFBK0I7QUFDN0MsYUFBTyxDQUFDO0FBQUEsSUFDWjtBQUFBLElBRUEsSUFBWSxhQUFhO0FBQ3JC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N0d4RDtBQThHUSxZQUFNLFlBQVcsK0JBQTBCLElBQUksSUFBSSxNQUFsQyxZQUF1QyxvQkFBSSxJQUFJO0FBQ2hFLGFBQU8sU0FBUyxPQUFPLE9BQU87QUFBQSxJQUNsQztBQUFBLElBQ0EsVUFBVSxDQUFDLFFBQXNCO0FBQzdCLHFCQUFlLENBQUMsRUFBRSxPQUFPLFlBQVksVUFBVSxJQUFJLElBQUksS0FBSyxTQUFTLElBQUksRUFBRSxNQUFNLGtCQUFrQixLQUFLLENBQUMsQ0FBQztBQUFBLElBQzlHO0FBQUEsSUFDQSxNQUFNLENBQUMsU0FBbUI7QUFDdEIsa0JBQWEsSUFBSSxJQUFJLFNBQVMsSUFBSSxFQUFHO0FBRXJDLGFBQU8saUJBQWlCLFlBQVksVUFBVSxNQUFNO0FBQ3BELHNCQUFnQixhQUFhLEtBQUs7QUFDbEMsc0JBQWdCLDhCQUE4QixLQUFLO0FBQ25ELHNCQUFnQixtQkFBbUIsS0FBSztBQUN4QyxxQkFBZSxLQUFLLE1BQU07QUFDMUIsZ0JBQVU7QUFBQSxJQUNkO0FBQUEsRUFDSjtBQUVBLEVBQUMsT0FBZSxRQUFRO0FBQ3hCLE1BQU0sa0JBQWtCLFNBQVMsZUFBZSxpQkFBaUI7QUFDakUsTUFBSSxtQkFBbUIsUUFBUSxnQkFBZ0IsZ0JBQWdCLE1BQU07QUFDakUsVUFBTSxLQUFLLEtBQUssTUFBTSxnQkFBZ0IsV0FBVyxDQUFDO0FBQUEsRUFDdEQsT0FDSztBQUNELFlBQVEsS0FBSyxrREFBa0Q7QUFBQSxFQUNuRTsiLAogICJuYW1lcyI6IFsibW9ycGhBdHRycyIsICJtb3JwaGRvbSIsICJjaGlsZHJlbk9ubHkiXQp9Cg==
