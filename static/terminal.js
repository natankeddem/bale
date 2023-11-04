export default {
  template: "<div></div>",
  mounted() {
    this.terminal = new Terminal(this.options);
    this.terminal.open(this.$el);
  },
  beforeDestroy() {
    this.terminal.dispose();
  },
  beforeUnmount() {
    this.terminal.dispose();
  },
  methods: {
    call_api_method(name, ...args) {
      this.terminal[name](...args);
    },
  },
  props: {
    options: Object,
  }
};
