/* Vita CRM
   Tabler bundles Bootstrap 5 and listens on document for data-bs-toggle
   (collapse, dropdown, modal, alert, tab). HTML inserted by HTMX keeps
   working through those listeners.

   Tooltips and popovers are not delegated. Create each instance once,
   including after htmx:afterSwap. Do not rebind listeners here.
*/
(function () {
  "use strict";

  function bootstrapApi() {
    if (!window.tabler || !window.tabler.bootstrap) {
      return null;
    }
    return window.tabler.bootstrap;
  }

  function initWidgets(root) {
    var api = bootstrapApi();
    if (!api || !root || typeof root.querySelectorAll !== "function") {
      return;
    }

    var nodes = [];
    if (typeof root.matches === "function" && root.matches("[data-bs-toggle='tooltip'], [data-bs-toggle='popover']")) {
      nodes.push(root);
    }
    root.querySelectorAll("[data-bs-toggle='tooltip'], [data-bs-toggle='popover']").forEach(function (node) {
      nodes.push(node);
    });

    nodes.forEach(function (node) {
      var Widget = node.getAttribute("data-bs-toggle") === "popover" ? api.Popover : api.Tooltip;
      if (!Widget.getInstance(node)) {
        new Widget(node);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initWidgets(document);
    });
  } else {
    initWidgets(document);
  }

  document.addEventListener("htmx:afterSwap", function (event) {
    var detail = event.detail || {};
    initWidgets(detail.target || event.target);
  });
})();
