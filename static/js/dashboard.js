(function () {
  "use strict";

  var select = document.getElementById("periodo");
  var dates = document.getElementById("periodo-fechas");
  if (select && dates) {
    select.addEventListener("change", function () {
      var custom = select.value === "personalizado";
      dates.hidden = !custom;
      if (!custom) {
        select.form.submit();
      }
    });
  }

  var node = document.getElementById("dashboard-data");
  if (!node || !window.Chart) {
    return;
  }
  var data = JSON.parse(node.textContent);
  var chart = window.Chart;
  chart.defaults.animation = false;
  chart.defaults.font.family = "inherit";
  chart.defaults.color = "#49566c";

  function formatGuaranies(value) {
    var amount = Math.round(Number(value) || 0);
    var digits = String(Math.abs(amount)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return "Gs. " + (amount < 0 ? "-" : "") + digits;
  }

  function abbreviate(value) {
    var amount = Number(value);
    if (!isFinite(amount)) {
      return "";
    }
    var abs = Math.abs(amount);
    if (abs >= 1000000) {
      return (amount / 1000000).toLocaleString("es-PY", { maximumFractionDigits: 1 }) + " M";
    }
    if (abs >= 1000) {
      return (amount / 1000).toLocaleString("es-PY", { maximumFractionDigits: 1 }) + " mil";
    }
    return amount.toLocaleString("es-PY", { maximumFractionDigits: 0 });
  }

  function baseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
    };
  }

  var evolution = document.getElementById("chart-evolution");
  if (evolution && data.evolution) {
    new chart(evolution, {
      type: "line",
      data: {
        labels: data.evolution.labels,
        datasets: [{
          label: "Valor de atenciones",
          data: data.evolution.values,
          borderColor: "#206bc4",
          backgroundColor: "#206bc4",
          pointRadius: 3,
          tension: 0.2,
        }],
      },
      options: Object.assign(baseOptions(), {
        scales: {
          y: {
            beginAtZero: true,
            ticks: { callback: abbreviate },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: function (items) {
                return data.evolution.fullLabels[items[0].dataIndex];
              },
              label: function (item) {
                return formatGuaranies(item.parsed.y);
              },
            },
          },
        },
      }),
    });
  }

  var services = document.getElementById("chart-services");
  if (services && data.services) {
    new chart(services, {
      type: "bar",
      data: {
        labels: data.services.labels,
        datasets: [{
          label: "Unidades",
          data: data.services.values,
          backgroundColor: "#0ca678",
        }],
      },
      options: Object.assign(baseOptions(), {
        indexAxis: "y",
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (item) {
                var units = item.parsed.x;
                return units === 1 ? "1 unidad" : units + " unidades";
              },
            },
          },
        },
      }),
    });
  }

  var split = document.getElementById("chart-split");
  if (split && data.split) {
    new chart(split, {
      type: "pie",
      data: {
        labels: data.split.labels.map(function (label, index) {
          return label + " (" + data.split.values[index] + " · " + data.split.percents[index] + " %)";
        }),
        datasets: [{
          data: data.split.values,
          backgroundColor: ["#206bc4", "#868e96"],
        }],
      },
      options: Object.assign(baseOptions(), {
        plugins: {
          tooltip: {
            callbacks: {
              label: function (item) {
                var index = item.dataIndex;
                return data.split.labels[index] + ": " +
                  data.split.values[index] + " (" + data.split.percents[index] + " %)";
              },
            },
          },
        },
      }),
    });
  }

  var statuses = document.getElementById("chart-statuses");
  if (statuses && data.statuses) {
    new chart(statuses, {
      type: "bar",
      data: {
        labels: data.statuses.labels,
        datasets: [{
          label: "Reservas",
          data: data.statuses.values,
          backgroundColor: data.statuses.colors,
        }],
      },
      options: Object.assign(baseOptions(), {
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (item) {
                var count = item.parsed.y;
                return count === 1 ? "1 reserva" : count + " reservas";
              },
            },
          },
        },
      }),
    });
  }
})();
