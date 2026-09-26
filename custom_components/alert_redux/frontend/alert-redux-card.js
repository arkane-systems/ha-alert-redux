var W=globalThis,q=W.ShadowRoot&&(W.ShadyCSS===void 0||W.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Z=Symbol(),de=new WeakMap,P=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==Z)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(q&&e===void 0){let i=t!==void 0&&t.length===1;i&&(e=de.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&de.set(t,e))}return e}toString(){return this.cssText}},he=n=>new P(typeof n=="string"?n:n+"",void 0,Z),k=(n,...e)=>{let t=n.length===1?n[0]:e.reduce((i,s,r)=>i+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(s)+n[r+1],n[0]);return new P(t,n,Z)},pe=(n,e)=>{if(q)n.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let i=document.createElement("style"),s=W.litNonce;s!==void 0&&i.setAttribute("nonce",s),i.textContent=t.cssText,n.appendChild(i)}},X=q?n=>n:n=>n instanceof CSSStyleSheet?(e=>{let t="";for(let i of e.cssRules)t+=i.cssText;return he(t)})(n):n;var{is:Le,defineProperty:Ve,getOwnPropertyDescriptor:je,getOwnPropertyNames:Fe,getOwnPropertySymbols:Be,getPrototypeOf:We}=Object,K=globalThis,ue=K.trustedTypes,qe=ue?ue.emptyScript:"",Ke=K.reactiveElementPolyfillSupport,R=(n,e)=>n,Q={toAttribute(n,e){switch(e){case Boolean:n=n?qe:null;break;case Object:case Array:n=n==null?n:JSON.stringify(n)}return n},fromAttribute(n,e){let t=n;switch(e){case Boolean:t=n!==null;break;case Number:t=n===null?null:Number(n);break;case Object:case Array:try{t=JSON.parse(n)}catch{t=null}}return t}},ge=(n,e)=>!Le(n,e),me={attribute:!0,type:String,converter:Q,reflect:!1,useDefault:!1,hasChanged:ge};Symbol.metadata??=Symbol("metadata"),K.litPropertyMetadata??=new WeakMap;var f=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=me){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let i=Symbol(),s=this.getPropertyDescriptor(e,i,t);s!==void 0&&Ve(this.prototype,e,s)}}static getPropertyDescriptor(e,t,i){let{get:s,set:r}=je(this.prototype,e)??{get(){return this[t]},set(o){this[t]=o}};return{get:s,set(o){let h=s?.call(this);r?.call(this,o),this.requestUpdate(e,h,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??me}static _$Ei(){if(this.hasOwnProperty(R("elementProperties")))return;let e=We(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(R("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(R("properties"))){let t=this.properties,i=[...Fe(t),...Be(t)];for(let s of i)this.createProperty(s,t[s])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[i,s]of t)this.elementProperties.set(i,s)}this._$Eh=new Map;for(let[t,i]of this.elementProperties){let s=this._$Eu(t,i);s!==void 0&&this._$Eh.set(s,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let s of i)t.unshift(X(s))}else e!==void 0&&t.push(X(e));return t}static _$Eu(e,t){let i=t.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return pe(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){let i=this.constructor.elementProperties.get(e),s=this.constructor._$Eu(e,i);if(s!==void 0&&i.reflect===!0){let r=(i.converter?.toAttribute!==void 0?i.converter:Q).toAttribute(t,i.type);this._$Em=e,r==null?this.removeAttribute(s):this.setAttribute(s,r),this._$Em=null}}_$AK(e,t){let i=this.constructor,s=i._$Eh.get(e);if(s!==void 0&&this._$Em!==s){let r=i.getPropertyOptions(s),o=typeof r.converter=="function"?{fromAttribute:r.converter}:r.converter?.fromAttribute!==void 0?r.converter:Q;this._$Em=s;let h=o.fromAttribute(t,r.type);this[s]=h??this._$Ej?.get(s)??h,this._$Em=null}}requestUpdate(e,t,i,s=!1,r){if(e!==void 0){let o=this.constructor;if(s===!1&&(r=this[e]),i??=o.getPropertyOptions(e),!((i.hasChanged??ge)(r,t)||i.useDefault&&i.reflect&&r===this._$Ej?.get(e)&&!this.hasAttribute(o._$Eu(e,i))))return;this.C(e,t,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:s,wrapped:r},o){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,o??t??this[e]),r!==!0||o!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),s===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[s,r]of this._$Ep)this[s]=r;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[s,r]of i){let{wrapped:o}=r,h=this[s];o!==!0||this._$AL.has(s)||h===void 0||this.C(s,void 0,r,h)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(t)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};f.elementStyles=[],f.shadowRootOptions={mode:"open"},f[R("elementProperties")]=new Map,f[R("finalized")]=new Map,Ke?.({ReactiveElement:f}),(K.reactiveElementVersions??=[]).push("2.1.2");var oe=globalThis,fe=n=>n,Y=oe.trustedTypes,_e=Y?Y.createPolicy("lit-html",{createHTML:n=>n}):void 0,Ae="$lit$",v=`lit$${Math.random().toFixed(9).slice(2)}$`,we="?"+v,Ye=`<${we}>`,x=document,N=()=>x.createComment(""),O=n=>n===null||typeof n!="object"&&typeof n!="function",ae=Array.isArray,Ge=n=>ae(n)||typeof n?.[Symbol.iterator]=="function",ee=`[ 	
\f\r]`,T=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ve=/-->/g,be=/>/g,y=RegExp(`>|${ee}(?:([^\\s"'>=/]+)(${ee}*=${ee}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),ye=/'/g,$e=/"/g,Se=/^(?:script|style|textarea|title)$/i,ce=n=>(e,...t)=>({_$litType$:n,strings:e,values:t}),l=ce(1),dt=ce(2),ht=ce(3),A=Symbol.for("lit-noChange"),a=Symbol.for("lit-nothing"),xe=new WeakMap,$=x.createTreeWalker(x,129);function ke(n,e){if(!ae(n)||!n.hasOwnProperty("raw"))throw Error("invalid template strings array");return _e!==void 0?_e.createHTML(e):e}var Je=(n,e)=>{let t=n.length-1,i=[],s,r=e===2?"<svg>":e===3?"<math>":"",o=T;for(let h=0;h<t;h++){let c=n[h],p,u,d=-1,g=0;for(;g<c.length&&(o.lastIndex=g,u=o.exec(c),u!==null);)g=o.lastIndex,o===T?u[1]==="!--"?o=ve:u[1]!==void 0?o=be:u[2]!==void 0?(Se.test(u[2])&&(s=RegExp("</"+u[2],"g")),o=y):u[3]!==void 0&&(o=y):o===y?u[0]===">"?(o=s??T,d=-1):u[1]===void 0?d=-2:(d=o.lastIndex-u[2].length,p=u[1],o=u[3]===void 0?y:u[3]==='"'?$e:ye):o===$e||o===ye?o=y:o===ve||o===be?o=T:(o=y,s=void 0);let _=o===y&&n[h+1].startsWith("/>")?" ":"";r+=o===T?c+Ye:d>=0?(i.push(p),c.slice(0,d)+Ae+c.slice(d)+v+_):c+v+(d===-2?h:_)}return[ke(n,r+(n[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},U=class n{constructor({strings:e,_$litType$:t},i){let s;this.parts=[];let r=0,o=0,h=e.length-1,c=this.parts,[p,u]=Je(e,t);if(this.el=n.createElement(p,i),$.currentNode=this.el.content,t===2||t===3){let d=this.el.content.firstChild;d.replaceWith(...d.childNodes)}for(;(s=$.nextNode())!==null&&c.length<h;){if(s.nodeType===1){if(s.hasAttributes())for(let d of s.getAttributeNames())if(d.endsWith(Ae)){let g=u[o++],_=s.getAttribute(d).split(v),B=/([.?@])?(.*)/.exec(g);c.push({type:1,index:r,name:B[2],strings:_,ctor:B[1]==="."?ie:B[1]==="?"?se:B[1]==="@"?ne:C}),s.removeAttribute(d)}else d.startsWith(v)&&(c.push({type:6,index:r}),s.removeAttribute(d));if(Se.test(s.tagName)){let d=s.textContent.split(v),g=d.length-1;if(g>0){s.textContent=Y?Y.emptyScript:"";for(let _=0;_<g;_++)s.append(d[_],N()),$.nextNode(),c.push({type:2,index:++r});s.append(d[g],N())}}}else if(s.nodeType===8)if(s.data===we)c.push({type:2,index:r});else{let d=-1;for(;(d=s.data.indexOf(v,d+1))!==-1;)c.push({type:7,index:r}),d+=v.length-1}r++}}static createElement(e,t){let i=x.createElement("template");return i.innerHTML=e,i}};function E(n,e,t=n,i){if(e===A)return e;let s=i!==void 0?t._$Co?.[i]:t._$Cl,r=O(e)?void 0:e._$litDirective$;return s?.constructor!==r&&(s?._$AO?.(!1),r===void 0?s=void 0:(s=new r(n),s._$AT(n,t,i)),i!==void 0?(t._$Co??=[])[i]=s:t._$Cl=s),s!==void 0&&(e=E(n,s._$AS(n,e.values),s,i)),e}var te=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:i}=this._$AD,s=(e?.creationScope??x).importNode(t,!0);$.currentNode=s;let r=$.nextNode(),o=0,h=0,c=i[0];for(;c!==void 0;){if(o===c.index){let p;c.type===2?p=new D(r,r.nextSibling,this,e):c.type===1?p=new c.ctor(r,c.name,c.strings,this,e):c.type===6&&(p=new re(r,this,e)),this._$AV.push(p),c=i[++h]}o!==c?.index&&(r=$.nextNode(),o++)}return $.currentNode=x,s}p(e){let t=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}},D=class n{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,s){this.type=2,this._$AH=a,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=E(this,e,t),O(e)?e===a||e==null||e===""?(this._$AH!==a&&this._$AR(),this._$AH=a):e!==this._$AH&&e!==A&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Ge(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==a&&O(this._$AH)?this._$AA.nextSibling.data=e:this.T(x.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:i}=e,s=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=U.createElement(ke(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(t);else{let r=new te(s,this),o=r.u(this.options);r.p(t),this.T(o),this._$AH=r}}_$AC(e){let t=xe.get(e.strings);return t===void 0&&xe.set(e.strings,t=new U(e)),t}k(e){ae(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,i,s=0;for(let r of e)s===t.length?t.push(i=new n(this.O(N()),this.O(N()),this,this.options)):i=t[s],i._$AI(r),s++;s<t.length&&(this._$AR(i&&i._$AB.nextSibling,s),t.length=s)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let i=fe(e).nextSibling;fe(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},C=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,s,r){this.type=1,this._$AH=a,this._$AN=void 0,this.element=e,this.name=t,this._$AM=s,this.options=r,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=a}_$AI(e,t=this,i,s){let r=this.strings,o=!1;if(r===void 0)e=E(this,e,t,0),o=!O(e)||e!==this._$AH&&e!==A,o&&(this._$AH=e);else{let h=e,c,p;for(e=r[0],c=0;c<r.length-1;c++)p=E(this,h[i+c],t,c),p===A&&(p=this._$AH[c]),o||=!O(p)||p!==this._$AH[c],p===a?e=a:e!==a&&(e+=(p??"")+r[c+1]),this._$AH[c]=p}o&&!s&&this.j(e)}j(e){e===a?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},ie=class extends C{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===a?void 0:e}},se=class extends C{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==a)}},ne=class extends C{constructor(e,t,i,s,r){super(e,t,i,s,r),this.type=5}_$AI(e,t=this){if((e=E(this,e,t,0)??a)===A)return;let i=this._$AH,s=e===a&&i!==a||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,r=e!==a&&(i===a||s);s&&this.element.removeEventListener(this.name,this,i),r&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},re=class{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){E(this,e)}};var Ze=oe.litHtmlPolyfillSupport;Ze?.(U,D),(oe.litHtmlVersions??=[]).push("3.3.3");var Ee=(n,e,t)=>{let i=t?.renderBefore??e,s=i._$litPart$;if(s===void 0){let r=t?.renderBefore??null;i._$litPart$=s=new D(e.insertBefore(N(),r),r,void 0,t??{})}return s._$AI(n),s};var le=globalThis,m=class extends f{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Ee(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return A}};m._$litElement$=!0,m.finalized=!0,le.litElementHydrateSupport?.({LitElement:m});var Xe=le.litElementPolyfillSupport;Xe?.({LitElement:m});(le.litElementVersions??=[]).push("4.2.2");var Qe="alert_redux",w=["emergency","critical","warning","notice","informational"],G={emergency:"Emergency",critical:"Critical",warning:"Warning",notice:"Notice",informational:"Informational"},et={emergency:"mdi:alarm-light",critical:"mdi:alert-octagon",warning:"mdi:alert",notice:"mdi:alert-circle-outline",informational:"mdi:information-outline"},L=n=>n.state==="active"||n.state==="ack",S=n=>n.startsWith(`${Qe}.`),z=n=>{if(typeof n!="string"||!n)return null;let e=new Date(n);return Number.isNaN(e.getTime())?null:e},H=n=>typeof n=="string"?n:null;function tt(n){let e=n.attributes,t=w.includes(e.priority)?e.priority:"informational";return{entityId:n.entity_id,state:n.state,name:H(e.friendly_name)??n.entity_id,icon:H(e.icon)??et[t],priority:t,kind:H(e.kind)??"",acknowledgeable:e.acknowledgeable!==!1,userDismissable:e.user_dismissable===!0,message:H(e.message),displayMessage:H(e.display_message),firingSince:z(e.firing_since),lastFired:z(e.last_fired),eventExpires:z(e.event_expires),noDataSince:z(e.no_data_since),missingInputs:Array.isArray(e.missing_inputs)?e.missing_inputs.map(String):[],snoozedUntil:z(e.snoozed_until),disabledUntil:z(e.disabled_until)}}var I=n=>Object.values(n.states).filter(e=>S(e.entity_id)).map(tt),Ce=n=>n?.getTime()??0;function Ie(n,e){return w.indexOf(n.priority)-w.indexOf(e.priority)||+(n.state==="ack")-+(e.state==="ack")||Ce(e.firingSince)-Ce(n.firingSince)||n.name.localeCompare(e.name)}function Me(n,e){return w.indexOf(n.priority)-w.indexOf(e.priority)||n.name.localeCompare(e.name)}var Pe={idle:"Idle",active:"Active",ack:"Acknowledged",no_data:"No data",disabled:"Disabled"},Re={manual:"Manual",state:"State",on_off:"On/off",threshold:"Threshold",template:"Template",trigger:"Trigger",event:"Bus event"},Te=(n,e)=>n.name.localeCompare(e.name),ze=[15,30,60,120,240];function Ne(n){if(!Array.isArray(n))return ze;let e=n.map(Number).filter(t=>t>0);return e.length?e:ze}var Oe=n=>n.displayMessage??n.message;function Ue(n,e=Date.now()){if(!n.eventExpires||!n.lastFired)return null;let t=n.eventExpires.getTime()-n.lastFired.getTime();return t<=0?null:Math.min(1,Math.max(0,(n.eventExpires.getTime()-e)/t))}function M(n){let e=Math.floor(Math.max(0,n)/6e4);if(e<1)return"less than a minute";if(e<60)return`${e} min`;let t=Math.floor(e/60);if(t<24)return e%60?`${t} h ${e%60} min`:`${t} h`;let i=Math.floor(t/24);return t%24?`${i} d ${t%24} h`:`${i} d`}var V=(n,e=Date.now())=>M(e-n.getTime()),De=(n,e=Date.now())=>M(Math.ceil((n.getTime()-e)/6e4)*6e4);function b(n,e){let t=new Date().toDateString()===n.toDateString();return n.toLocaleString(e,t?{hour:"numeric",minute:"2-digit"}:{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})}var J=k`
  :host {
    --ar-emergency: var(--alert-redux-emergency-color, #e53935);
    --ar-critical: var(--alert-redux-critical-color, #fb8c00);
    --ar-warning: var(--alert-redux-warning-color, #fdd835);
    --ar-notice: var(--alert-redux-notice-color, #43a047);
    --ar-informational: var(--alert-redux-informational-color, #1e88e5);
    --ar-stripe-dark: #212121;
    display: block;
  }

  .p-emergency { --c: var(--ar-emergency); }
  .p-critical { --c: var(--ar-critical); }
  .p-warning { --c: var(--ar-warning); }
  .p-notice { --c: var(--ar-notice); }
  .p-informational { --c: var(--ar-informational); }

  button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 18px;
    border: 1px solid var(--divider-color);
    background: transparent;
    color: var(--primary-text-color);
    font: inherit;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    --mdc-icon-size: 18px;
  }
  button:hover {
    background: color-mix(in srgb, var(--primary-text-color) 6%, transparent);
  }
  button:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  button.primary {
    border-color: transparent;
    background: var(--primary-color);
    color: var(--text-primary-color, #fff);
  }
  button.primary:hover {
    background: color-mix(in srgb, var(--primary-color) 85%, #000);
  }

  button .caret {
    margin: 0 -6px 0 -4px;
  }
  button.snoozed {
    border-color: color-mix(in srgb, var(--primary-color) 60%, var(--divider-color));
    background: color-mix(in srgb, var(--primary-color) 10%, transparent);
  }

  /* A row of choices opened below a control, e.g. snooze durations. */
  .choices {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    align-items: center;
    gap: 6px;
    padding-top: 8px;
    border-top: 1px dashed var(--divider-color);
  }
  .choices .label {
    flex-basis: 100%;
    text-align: right;
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }
  .choices .break {
    flex-basis: 100%;
    height: 0;
  }
  button.chip-button {
    padding: 4px 12px;
    border-radius: 14px;
    font-size: 0.8rem;
    --mdc-icon-size: 16px;
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 4px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--secondary-text-color);
    --mdc-icon-size: 16px;
  }
`,He=k`
  .content {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
  }
  .content.has-header {
    padding-top: 0;
  }

  /* --- One firing alert --- */
  .alert {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 12px 12px 22px;
    border: 1px solid var(--divider-color);
    border-radius: 12px;
    background: color-mix(in srgb, var(--c) 6%, transparent);
    overflow: hidden;
  }

  .alert::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 8px;
    background: var(--c);
  }

  /* Warning: caution striping on the bar. */
  .alert.p-warning::before {
    width: 10px;
    background: repeating-linear-gradient(
      -45deg,
      var(--c) 0 6px,
      var(--ar-stripe-dark) 6px 12px
    );
  }
  .alert.p-warning {
    padding-left: 24px;
  }

  /* Emergency and Critical: a glow in the priority colour. It's drawn outside the
     box, so the box itself doesn't clip it; an active Emergency pulses. */
  .alert.p-emergency,
  .alert.p-critical {
    overflow: visible;
    border-color: var(--c);
  }
  .alert.p-emergency::before,
  .alert.p-critical::before {
    border-radius: 11px 0 0 11px;
  }
  .alert.p-emergency {
    box-shadow: 0 0 14px 2px color-mix(in srgb, var(--c) 55%, transparent);
  }
  .alert.p-critical {
    box-shadow: 0 0 10px 1px color-mix(in srgb, var(--c) 45%, transparent);
  }
  .alert.p-emergency.active {
    animation: glow-pulse 2s ease-in-out infinite;
  }
  @keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 8px 1px color-mix(in srgb, var(--c) 45%, transparent); }
    50% { box-shadow: 0 0 20px 5px color-mix(in srgb, var(--c) 70%, transparent); }
  }
  @media (prefers-reduced-motion: reduce) {
    .alert.p-emergency.active { animation: none; }
  }

  /* Acknowledged: the same colours, with the emphasis toned down. */
  .alert.ack {
    background: color-mix(in srgb, var(--c) 3%, transparent);
  }
  .alert.ack.p-emergency,
  .alert.ack.p-critical {
    border-color: color-mix(in srgb, var(--c) 50%, var(--divider-color));
    box-shadow: 0 0 5px 0 color-mix(in srgb, var(--c) 25%, transparent);
  }
  .alert.ack::before {
    opacity: 0.55;
  }
  .alert.ack .chip {
    opacity: 0.7;
  }

  /* Event alerts: the time left, as a bar along the foot of the box that drains
     as the duration runs out. It moves a step per render, smoothed by the
     transition. */
  .progress {
    position: absolute;
    inset: auto 0 0 0;
    height: 4px;
    border-radius: 0 0 11px 11px;
    overflow: hidden;
    background: color-mix(in srgb, var(--c) 15%, transparent);
  }
  .progress-fill {
    height: 100%;
    background: var(--c);
    transition: width 1s linear;
  }
  .alert.p-warning .progress-fill {
    background: color-mix(in oklch, var(--c) 80%, #000);
  }
  .alert.ack .progress-fill {
    opacity: 0.55;
  }
  @media (prefers-reduced-motion: reduce) {
    .progress-fill { transition: none; }
  }

  .head {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .chip {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    border: 2px solid var(--c);
    background: color-mix(in srgb, var(--c) 15%, transparent);
    color: var(--c);
    cursor: pointer;
    --mdc-icon-size: 22px;
  }
  /* Yellow and orange are hard to read on a light card; darken the glyph. */
  .light .p-warning .chip,
  .light .p-critical .chip {
    color: color-mix(in oklch, var(--c) 60%, #000);
  }

  .title {
    min-width: 0;
  }
  .name {
    font-weight: 600;
    font-size: 1.05rem;
    line-height: 1.3;
    color: var(--primary-text-color);
    cursor: pointer;
    overflow-wrap: anywhere;
  }
  .meta {
    font-size: 0.85rem;
    color: var(--secondary-text-color);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    column-gap: 6px;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 0 6px;
    border-radius: 8px;
    font-size: 0.75rem;
    line-height: 1.4rem;
    background: color-mix(in srgb, var(--warning-color, #ffa600) 18%, transparent);
    color: var(--primary-text-color);
    --mdc-icon-size: 14px;
  }

  .message {
    color: var(--primary-text-color);
    white-space: pre-line;
    overflow-wrap: anywhere;
  }

  .controls {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 8px;
  }

  /* --- Empty state, no-data section, version banner --- */
  .empty {
    color: var(--secondary-text-color);
    font-size: 0.9rem;
  }

  .no-data {
    display: flex;
    flex-direction: column;
    border: 1px dashed var(--divider-color);
    border-radius: 12px;
  }
  .no-data-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    cursor: pointer;
    --mdc-icon-size: 20px;
  }
  .no-data-row + .no-data-row {
    border-top: 1px solid var(--divider-color);
  }
  .no-data-row ha-icon {
    color: var(--c);
    opacity: 0.8;
    flex-shrink: 0;
  }
  .no-data-row .text {
    min-width: 0;
    flex: 1;
  }
  .no-data-row .name {
    font-size: 0.95rem;
    font-weight: 500;
  }
  .no-data-row .meta {
    font-size: 0.8rem;
  }

  /* Disabled alerts aren't shown on this card, only counted (spec §13.1). */
  .disabled-line {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.85rem;
    color: var(--secondary-text-color);
    --mdc-icon-size: 16px;
  }

  .banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--info-color, #039be5) 14%, transparent);
    color: var(--primary-text-color);
    font-size: 0.9rem;
  }
  .banner span {
    flex: 1;
  }
`;var it=3e4,st=1e3,j=class extends m{constructor(){super();this._hasProgress=!1;this._versionChecked=!1;this._busy=new Set}static getStubConfig(){return{}}static getConfigForm(){return{schema:[{name:"title",selector:{text:{}}}]}}setConfig(t){this._config=t}getCardSize(){if(!this.hass)return 2;let t=I(this.hass),i=t.filter(L).length,s=t.filter(o=>o.state==="no_data").length,r=t.some(o=>o.state==="disabled");return 1+Math.max(1,i*3)+(s?1+s:0)+(r?1:0)}getGridOptions(){return{columns:12,min_columns:6}}connectedCallback(){super.connectedCallback(),this._tick=window.setInterval(()=>this.requestUpdate(),it)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this._tick),window.clearTimeout(this._progressTick),this._progressTick=void 0}shouldUpdate(t){if(t.size!==1||!t.has("hass"))return!0;let i=t.get("hass");if(!i||!this.hass||i.themes?.darkMode!==this.hass.themes?.darkMode)return!0;let s=this.hass.states,r=i.states;for(let o in s)if(S(o)&&s[o]!==r[o])return!0;for(let o in r)if(S(o)&&!(o in s))return!0;return!1}updated(){this._hasProgress&&this._progressTick===void 0&&this.isConnected&&(this._progressTick=window.setTimeout(()=>{this._progressTick=void 0,this.requestUpdate()},st)),this.hass&&!this._versionChecked&&(this._versionChecked=!0,this._checkVersion())}async _checkVersion(){try{let{version:t}=await this.hass.callWS({type:"alert_redux/info"});t!=="0.6.0"&&(this._serverVersion=t)}catch{}}render(){if(this._hasProgress=!1,!this.hass||!this._config)return a;let t=I(this.hass),i=t.filter(L).sort(Ie),s=t.filter(c=>c.state==="no_data").sort(Me),r=t.filter(c=>c.state==="disabled").length,o=this._config.title,h=this.hass.themes?.darkMode??!1;return l`
      <ha-card .header=${o||void 0}>
        <div class="content ${o?"has-header":""} ${h?"dark":"light"}">
          ${this._serverVersion?this._renderBanner(this._serverVersion):a}
          ${i.length?i.map(c=>this._renderAlert(c)):l`<div class="empty">No alerts are firing.</div>`}
          ${s.length?this._renderNoData(s):a}
          ${r?l`<div class="disabled-line">
                <ha-icon icon="mdi:bell-off-outline"></ha-icon>${r}
                ${r===1?"alert":"alerts"} disabled
              </div>`:a}
        </div>
      </ha-card>
    `}_renderBanner(t){return l`
      <div class="banner" role="status">
        <ha-icon icon="mdi:update"></ha-icon>
        <span>Alert Redux has been updated to ${t}. Reload to use the new card.</span>
        <button class="primary" @click=${()=>location.reload()}>Reload</button>
      </div>
    `}_renderAlert(t){let i=Oe(t),s=this.hass?.locale?.language,r=t.firingSince;return l`
      <div class="alert p-${t.priority} ${t.state}">
        <div class="head">
          <div class="chip" @click=${()=>this._moreInfo(t)}>
            <ha-icon .icon=${t.icon}></ha-icon>
          </div>
          <div class="title">
            <div class="name" @click=${()=>this._moreInfo(t)}>${t.name}</div>
            <div class="meta">
              <span>${G[t.priority]}</span>
              ${r?l`<span>·</span>
                    <span title=${r.toLocaleString(s)}
                      >firing for ${V(r)} (since ${b(r,s)})</span
                    >`:a}
              ${t.noDataSince?l`<span
                    class="badge"
                    title=${t.missingInputs.length?`Missing: ${t.missingInputs.join(", ")}`:"Waiting for data"}
                    ><ha-icon icon="mdi:lan-disconnect"></ha-icon>No data</span
                  >`:a}
            </div>
          </div>
        </div>
        ${i?l`<div class="message">${i}</div>`:a}
        ${this._renderControls(t)}
        ${this._renderProgress(t)}
      </div>
    `}_renderProgress(t){let i=Ue(t);if(i===null||!t.eventExpires)return a;this._hasProgress=!0;let s=b(t.eventExpires,this.hass?.locale?.language);return l`
      <div class="progress" title="Ends at ${s}">
        <div class="progress-fill" style="width: ${(i*100).toFixed(2)}%"></div>
      </div>
    `}_renderControls(t){let i=this._busy.has(t.entityId),s=t.kind==="manual"&&t.userDismissable;if(!t.acknowledgeable&&!s)return a;let r=t.state==="ack"&&t.snoozedUntil,o=this._snoozeMenu===t.entityId;return l`
      <div class="controls">
        ${s?l`<button
              ?disabled=${i}
              @click=${()=>this._call(t,"dismiss")}
            >
              <ha-icon icon="mdi:close"></ha-icon>Dismiss
            </button>`:a}
        ${t.acknowledgeable?l`<button
              class=${r?"snoozed":""}
              ?disabled=${i}
              aria-expanded=${o?"true":"false"}
              title=${r?`Snoozed until ${this._time(t.snoozedUntil)}`:"Snooze"}
              @click=${()=>this._toggleSnoozeMenu(t)}
            >
              <ha-icon icon="mdi:alarm-snooze"></ha-icon>${r?`Snoozed \xB7 ${De(t.snoozedUntil)}`:"Snooze"}<ha-icon
                class="caret"
                icon=${o?"mdi:menu-up":"mdi:menu-down"}
              ></ha-icon>
            </button>`:a}
        ${!t.acknowledgeable||r?a:t.state==="ack"?l`<button
                ?disabled=${i}
                title="Remove the acknowledgement"
                @click=${()=>this._call(t,"unack")}
              >
                <ha-icon icon="mdi:check-circle"></ha-icon>Acknowledged
              </button>`:l`<button
                class="primary"
                ?disabled=${i}
                @click=${()=>this._call(t,"ack")}
              >
                <ha-icon icon="mdi:check"></ha-icon>Acknowledge
              </button>`}
      </div>
      ${o?this._renderSnoozeMenu(t,i):a}
    `}_renderSnoozeMenu(t,i){let s=t.state==="ack"&&t.snoozedUntil;return l`
      <div class="choices" role="group" aria-label="Snooze for">
        <span class="label">${s?"Snooze again for":"Snooze for"}</span>
        ${Ne(this._config?.snooze_durations).map(r=>l`<button
            class="chip-button"
            ?disabled=${i}
            @click=${()=>this._snooze(t,r)}
          >
            ${M(r*6e4)}
          </button>`)}
        ${s?l`<span class="break"></span>
              <button
                class="chip-button"
                ?disabled=${i}
                title="Stay acknowledged until the alert stops firing"
                @click=${()=>this._menuCall(t,"ack")}
              >
                <ha-icon icon="mdi:check-circle"></ha-icon>Keep acknowledged
              </button>
              <button
                class="chip-button"
                ?disabled=${i}
                title="Remove the snooze and the acknowledgement"
                @click=${()=>this._menuCall(t,"unack")}
              >
                <ha-icon icon="mdi:alarm-off"></ha-icon>Unsnooze
              </button>`:a}
      </div>
    `}_toggleSnoozeMenu(t){this._snoozeMenu=this._snoozeMenu===t.entityId?void 0:t.entityId}_snooze(t,i){this._snoozeMenu=void 0,this._call(t,"snooze",{duration:{minutes:i}})}_menuCall(t,i){this._snoozeMenu=void 0,this._call(t,i)}_time(t){return b(t,this.hass?.locale?.language)}_renderNoData(t){return l`
      <div class="section-title">
        <ha-icon icon="mdi:lan-disconnect"></ha-icon>No data (${t.length})
      </div>
      <div class="no-data">
        ${t.map(i=>l`
            <div class="no-data-row p-${i.priority}" @click=${()=>this._moreInfo(i)}>
              <ha-icon .icon=${i.icon}></ha-icon>
              <div class="text">
                <div class="name">${i.name}</div>
                <div class="meta">
                  ${i.missingInputs.length?`Missing: ${i.missingInputs.join(", ")}`:"Waiting for data"}${i.noDataSince?` \xB7 for ${V(i.noDataSince)}`:""}
                </div>
              </div>
            </div>
          `)}
      </div>
    `}async _call(t,i,s={}){if(this.hass){this._busy=new Set(this._busy).add(t.entityId);try{await this.hass.callService("alert_redux",i,{entity_id:t.entityId,...s})}catch(r){this._fire("hass-notification",{message:r?.message??String(r)})}finally{let r=new Set(this._busy);r.delete(t.entityId),this._busy=r}}}_moreInfo(t){this._fire("hass-more-info",{entityId:t.entityId})}_fire(t,i){this.dispatchEvent(new CustomEvent(t,{detail:i,bubbles:!0,composed:!0}))}};j.properties={hass:{attribute:!1},_config:{state:!0},_serverVersion:{state:!0},_busy:{state:!0},_snoozeMenu:{state:!0}},j.styles=[J,He];customElements.get("alert-redux-card")||(customElements.define("alert-redux-card",j),window.customCards=window.customCards??[],window.customCards.push({type:"alert-redux-card",name:"Alert Redux",description:"Shows firing Alert Redux alerts, and lets you acknowledge them."}),console.info("%c ALERT-REDUX-CARD %c 0.6.0 ","color:white;background:#b71c1c",""));var nt=3e4,rt=[60,240,480,1440,10080],F=class extends m{constructor(){super(),this._busy=new Set,this._untilOpen=!1}static getStubConfig(){return{}}static getConfigForm(){return{schema:[{name:"title",selector:{text:{}}}]}}setConfig(e){this._config=e}getCardSize(){return 1+(this.hass?I(this.hass).length:1)}getGridOptions(){return{columns:12,min_columns:6}}connectedCallback(){super.connectedCallback(),this._tick=window.setInterval(()=>this.requestUpdate(),nt)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this._tick)}shouldUpdate(e){if(e.size!==1||!e.has("hass"))return!0;let t=e.get("hass");if(!t||!this.hass||t.user?.is_admin!==this.hass.user?.is_admin)return!0;let i=this.hass.states,s=t.states;for(let r in i)if(S(r)&&i[r]!==s[r])return!0;for(let r in s)if(S(r)&&!(r in i))return!0;return!1}render(){if(!this.hass||!this._config)return a;let e=I(this.hass),t=this._config.title;return l`
      <ha-card .header=${t||void 0}>
        <div class="content ${t?"has-header":""}">
          ${e.length?w.map(i=>{let s=e.filter(r=>r.priority===i).sort(Te);return s.length?l`
                  <div class="section-title p-${i}">
                    <span class="dot"></span>${G[i]} (${s.length})
                  </div>
                  <div class="group">${s.map(r=>this._renderRow(r))}</div>
                `:a}):l`<div class="empty">No alerts are configured.</div>`}
        </div>
      </ha-card>
    `}_renderRow(e){let t=this.hass?.user?.is_admin??!1,i=this._busy.has(e.entityId),s=e.state==="disabled";return l`
      <div class="row p-${e.priority} ${e.state}">
        <div class="line">
          <ha-icon .icon=${e.icon} @click=${()=>this._moreInfo(e)}></ha-icon>
          <div class="text">
            <div class="name" @click=${()=>this._moreInfo(e)}>${e.name}</div>
            <div class="meta">
              ${this._kind(e)} ·
              <span class="state ${e.state}">${this._state(e)}</span>
              ${this._detail(e)}
            </div>
          </div>
          ${t?l`<div class="controls">
                ${s?l`<button
                      class="primary"
                      ?disabled=${i}
                      @click=${()=>this._call(e,"enable")}
                    >
                      <ha-icon icon="mdi:bell-outline"></ha-icon>Enable
                    </button>`:l`<button ?disabled=${i} @click=${()=>this._call(e,"disable")}>
                      <ha-icon icon="mdi:bell-off-outline"></ha-icon>Disable
                    </button>`}
                <button
                  ?disabled=${i}
                  aria-expanded=${this._menu===e.entityId?"true":"false"}
                  @click=${()=>this._toggleMenu(e)}
                >
                  <ha-icon icon="mdi:timer-pause-outline"></ha-icon>Suspend<ha-icon
                    class="caret"
                    icon=${this._menu===e.entityId?"mdi:menu-up":"mdi:menu-down"}
                  ></ha-icon>
                </button>
              </div>`:a}
        </div>
        ${t&&this._menu===e.entityId?this._renderMenu(e,i):a}
      </div>
    `}_renderMenu(e,t){return l`
      <div class="choices" role="group" aria-label="Suspend for">
        <span class="label">Suspend for</span>
        ${rt.map(i=>l`<button
            class="chip-button"
            ?disabled=${t}
            @click=${()=>this._suspend(e,{duration:{minutes:i}})}
          >
            ${i===10080?"1 week":M(i*6e4)}
          </button>`)}
        <button
          class="chip-button"
          ?disabled=${t}
          aria-expanded=${this._untilOpen?"true":"false"}
          @click=${()=>this._untilOpen=!this._untilOpen}
        >
          Until…
        </button>
        ${this._untilOpen?l`<div class="until">
              <input
                type="datetime-local"
                aria-label="Suspend until"
                .value=${this._defaultUntil()}
              />
              <button class="primary chip-button" ?disabled=${t} @click=${()=>this._suspendUntil(e)}>Suspend</button>
            </div>`:a}
      </div>
    `}_kind(e){let t=this.hass?.states[e.entityId],i=t?this.hass?.formatEntityAttributeValue?.(t,"kind"):void 0;return i&&i!==e.kind?i:Re[e.kind]??e.kind}_state(e){let t=this.hass?.states[e.entityId],i=t?this.hass?.formatEntityState?.(t):void 0;return i&&i!==e.state?i:Pe[e.state]??e.state}_detail(e){let t=this.hass?.locale?.language;return e.state==="disabled"?e.disabledUntil?l`until ${b(e.disabledUntil,t)}`:a:e.state==="ack"&&e.snoozedUntil?l`snoozed until ${b(e.snoozedUntil,t)}`:L(e)&&e.firingSince?l`since ${b(e.firingSince,t)}`:e.state==="no_data"&&e.noDataSince?l`for ${V(e.noDataSince)}`:a}_defaultUntil(){let e=new Date;e.setDate(e.getDate()+1),e.setHours(8,0,0,0);let t=i=>String(i).padStart(2,"0");return`${e.getFullYear()}-${t(e.getMonth()+1)}-${t(e.getDate())}T${t(e.getHours())}:${t(e.getMinutes())}`}_toggleMenu(e){this._untilOpen=!1,this._menu=this._menu===e.entityId?void 0:e.entityId}_suspendUntil(e){let t=this.renderRoot.querySelector('input[type="datetime-local"]');if(!t?.value)return;let i=new Date(t.value);Number.isNaN(i.getTime())||this._suspend(e,{until:i.toISOString()})}_suspend(e,t){this._menu=void 0,this._untilOpen=!1,this._call(e,"suspend",t)}async _call(e,t,i={}){if(this.hass){this._busy=new Set(this._busy).add(e.entityId);try{await this.hass.callService("alert_redux",t,{entity_id:e.entityId,...i})}catch(s){this._fire("hass-notification",{message:s?.message??String(s)})}finally{let s=new Set(this._busy);s.delete(e.entityId),this._busy=s}}}_moreInfo(e){this._fire("hass-more-info",{entityId:e.entityId})}_fire(e,t){this.dispatchEvent(new CustomEvent(e,{detail:t,bubbles:!0,composed:!0}))}};F.properties={hass:{attribute:!1},_config:{state:!0},_busy:{state:!0},_menu:{state:!0},_untilOpen:{state:!0}},F.styles=[J,k`
      .content {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 16px;
      }
      .content.has-header {
        padding-top: 0;
      }
      .section-title .dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--c);
      }
      .group {
        display: flex;
        flex-direction: column;
        border: 1px solid var(--divider-color);
        border-radius: 12px;
        margin-bottom: 4px;
      }
      .row {
        padding: 8px 12px;
      }
      .row + .row {
        border-top: 1px solid var(--divider-color);
      }
      .line {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px 10px;
      }
      .line > ha-icon {
        color: var(--c);
        flex-shrink: 0;
        cursor: pointer;
        --mdc-icon-size: 22px;
      }
      .text {
        flex: 1;
        min-width: 150px;
      }
      .name {
        font-weight: 500;
        color: var(--primary-text-color);
        cursor: pointer;
        overflow-wrap: anywhere;
      }
      .meta {
        font-size: 0.8rem;
        color: var(--secondary-text-color);
      }
      .state {
        display: inline-block;
        padding: 0 7px;
        border-radius: 8px;
        line-height: 1.3rem;
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--primary-text-color);
        background: color-mix(in srgb, var(--primary-text-color) 8%, transparent);
      }
      .state.active {
        background: color-mix(in srgb, var(--c) 30%, transparent);
      }
      .state.ack {
        background: color-mix(in srgb, var(--c) 14%, transparent);
      }
      .state.no_data {
        background: color-mix(in srgb, var(--warning-color, #ffa600) 20%, transparent);
      }
      .row.disabled > .line > ha-icon,
      .row.disabled .name {
        opacity: 0.55;
      }
      .controls {
        display: flex;
        gap: 6px;
        margin-left: auto;
      }
      .controls button {
        padding: 4px 12px;
        font-size: 0.8rem;
        --mdc-icon-size: 16px;
      }
      .choices {
        margin-top: 8px;
      }
      .until {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        align-items: center;
        gap: 6px;
        flex-basis: 100%;
      }
      input[type="datetime-local"] {
        font: inherit;
        font-size: 0.85rem;
        padding: 3px 8px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color, transparent);
        color: var(--primary-text-color);
        color-scheme: light dark;
      }
      .empty {
        color: var(--secondary-text-color);
        font-size: 0.9rem;
      }
    `];customElements.get("alert-redux-admin-card")||(customElements.define("alert-redux-admin-card",F),window.customCards=window.customCards??[],window.customCards.push({type:"alert-redux-admin-card",name:"Alert Redux admin",description:"Lists every Alert Redux alert, and lets admins disable, enable, and suspend them."}));
