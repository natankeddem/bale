export default {
  template: "<div></div>",
  async mounted() {
    await this.load_resource("https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css");
    this.terminal = new Terminal(this.options);
    this.terminal.open(this.$el);
    // this.$emit("init", {});
    const connectInterval = setInterval(async () => {
      if (window.socket.id === undefined) return;
      this.$emit("init", { socket_id: window.socket.id });
      clearInterval(connectInterval);
    }, 100);
  },
  beforeDestroy() {
    this.terminal.dispose();
  },
  beforeUnmount() {
    this.terminal.dispose();
  },
  methods: {
    load_resource(url) {
      return new Promise((resolve, reject) => {
        const dataAttribute = `data-${url.split("/").pop().replace(/\./g, "-")}`;
        if (document.querySelector(`[${dataAttribute}]`)) {
          resolve();
          return;
        }
        let element;
        if (url.endsWith(".css")) {
          element = document.createElement("link");
          element.setAttribute("rel", "stylesheet");
          element.setAttribute("href", url);
        } else if (url.endsWith(".js")) {
          element = document.createElement("script");
          element.setAttribute("src", url);
        }
        element.setAttribute(dataAttribute, "");
        document.head.appendChild(element);
        element.onload = resolve;
        element.onerror = reject;
      });
    },
    call_api_method(name, ...args) {
      this.terminal[name](...args);
    },
  },
  props: {
    options: Object,
  }
};
