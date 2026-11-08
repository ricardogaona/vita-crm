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

  function blurIfInside(modalEl) {
    var active = document.activeElement;
    if (active && modalEl.contains(active) && typeof active.blur === "function") {
      active.blur();
    }
  }

  function hideNewClientModal(modalEl, modal) {
    modalEl.addEventListener(
      "hidden.bs.modal",
      function () {
        var body = document.getElementById("new-client-modal-body");
        if (body) {
          body.replaceChildren();
        }
      },
      { once: true }
    );
    modal.hide();
    // The focus trap turns off as hide() starts. Blurring earlier snaps
    // focus back into the form and the dialog stays open.
    blurIfInside(modalEl);
  }

  document.addEventListener("closeNewClientModal", function () {
    var modalEl = document.getElementById("new-client-modal");
    var api = bootstrapApi();
    if (!modalEl || !api || !api.Modal) {
      return;
    }
    var modal = api.Modal.getInstance(modalEl);
    if (!modal) {
      return;
    }
    // HTMX is still inside afterSettle when this event fires. Closing on
    // the next turn runs after that settle releases focus.
    window.setTimeout(function () {
      if (!modal._isTransitioning) {
        hideNewClientModal(modalEl, modal);
        return;
      }
      function afterTransition() {
        modalEl.removeEventListener("shown.bs.modal", afterTransition);
        modalEl.removeEventListener("hidden.bs.modal", afterTransition);
        if (modal._isShown) {
          hideNewClientModal(modalEl, modal);
        }
      }
      modalEl.addEventListener("shown.bs.modal", afterTransition);
      modalEl.addEventListener("hidden.bs.modal", afterTransition);
    }, 0);
  });
})();
