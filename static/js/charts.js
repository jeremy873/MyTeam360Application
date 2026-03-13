/*
  MyTeam360 — Chart.js Configurations
  © 2026 Praxis Holdings LLC. PROPRIETARY AND CONFIDENTIAL.
*/

const MT360Charts = {
  // ═══ SHARED DEFAULTS ═══
  colors: {
    purple: '#5E81F4',
    purpleLight: '#7BA0F6',
    blue: '#54C7EC',
    blueLight: '#7DD8F2',
    teal: '#54C7EC',
    green: '#7CE7AC',
    amber: '#F4BE5E',
    red: '#FF808B',
    text: '#8181A5',
    textDim: '#B8B8D0',
    grid: 'rgba(0,0,0,0.04)',
    white: '#FFFFFF',
  },

  defaultFont: { family: "'DM Sans', sans-serif", size: 11, weight: 500 },

  gridConfig() {
    return {
      color: this.colors.grid,
      drawBorder: false,
      tickColor: 'transparent',
    };
  },

  tooltipConfig() {
    return {
      backgroundColor: 'rgba(28,29,33,0.95)',
      borderColor: 'rgba(0,0,0,0.1)',
      borderWidth: 1,
      titleFont: { family: "'Outfit', sans-serif", size: 13, weight: 700 },
      bodyFont: { family: "'DM Sans', sans-serif", size: 12 },
      padding: 12,
      cornerRadius: 10,
      displayColors: true,
      boxPadding: 4,
    };
  },

  // ═══ AREA CHART (Revenue/Sales Overview) ═══
  createAreaChart(canvasId, labels, data, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 250);
    gradient.addColorStop(0, 'rgba(94,129,244,0.15)');
    gradient.addColorStop(1, 'rgba(94,129,244,0.01)');

    return new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: options.label || 'Revenue',
          data,
          borderColor: this.colors.purple,
          backgroundColor: gradient,
          borderWidth: 2.5,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: this.colors.purple,
          pointHoverBorderColor: '#fff',
          pointHoverBorderWidth: 2,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 800, easing: 'easeOutQuart' },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: this.tooltipConfig(),
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: this.colors.textDim, font: this.defaultFont },
          },
          y: {
            grid: this.gridConfig(),
            ticks: {
              color: this.colors.textDim,
              font: this.defaultFont,
              callback: (v) => options.prefix ? options.prefix + v.toLocaleString() : v.toLocaleString(),
            },
            beginAtZero: true,
          }
        }
      }
    });
  },

  // ═══ BAR CHART (Monthly Deals, etc.) ═══
  createBarChart(canvasId, labels, data, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const gradient = ctx.getContext('2d').createLinearGradient(0, 200, 0, 0);
    gradient.addColorStop(0, 'rgba(94,129,244,0.3)');
    gradient.addColorStop(1, 'rgba(94,129,244,0.8)');

    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: options.label || 'Deals',
          data,
          backgroundColor: gradient,
          borderRadius: 6,
          borderSkipped: false,
          barPercentage: 0.6,
          categoryPercentage: 0.7,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 800, easing: 'easeOutQuart' },
        plugins: {
          legend: { display: false },
          tooltip: this.tooltipConfig(),
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: this.colors.textDim, font: this.defaultFont },
          },
          y: {
            grid: this.gridConfig(),
            ticks: { color: this.colors.textDim, font: this.defaultFont },
            beginAtZero: true,
          }
        }
      }
    });
  },

  // ═══ DONUT / GAUGE CHART ═══
  createGaugeChart(canvasId, value, max = 100, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const color = options.color || this.colors.purple;

    return new Chart(ctx, {
      type: 'doughnut',
      data: {
        datasets: [{
          data: [value, max - value],
          backgroundColor: [color, 'rgba(0,0,0,0.04)'],
          borderWidth: 0,
          borderRadius: 8,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        cutout: '78%',
        rotation: -90,
        circumference: 180,
        animation: { duration: 1000, easing: 'easeOutQuart' },
        plugins: {
          legend: { display: false },
          tooltip: { enabled: false },
        }
      }
    });
  },

  // ═══ DONUT CHART (full circle) ═══
  createDonutChart(canvasId, labels, data, colors) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: colors || [this.colors.purple, this.colors.blue, this.colors.teal, this.colors.green, this.colors.amber],
          borderWidth: 0,
          borderRadius: 4,
          spacing: 3,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        cutout: '70%',
        animation: { duration: 800, easing: 'easeOutQuart' },
        plugins: {
          legend: { display: false },
          tooltip: this.tooltipConfig(),
        }
      }
    });
  },

  // ═══ SPARKLINE (mini line for stat cards) ═══
  createSparkline(canvasId, data, color) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    color = color || this.colors.purple;
    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 40);
    gradient.addColorStop(0, color.replace(')', ',0.3)').replace('rgb', 'rgba'));
    gradient.addColorStop(1, 'transparent');

    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map((_, i) => i),
        datasets: [{
          data,
          borderColor: color,
          backgroundColor: gradient,
          borderWidth: 1.5,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 600 },
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          x: { display: false },
          y: { display: false }
        }
      }
    });
  },

  // ═══ LINE CHART (Multi-line for analytics) ═══
  createLineChart(canvasId, labels, datasets) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const chartColors = [this.colors.purple, this.colors.green, this.colors.red, this.colors.amber];

    return new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: datasets.map((ds, i) => ({
          label: ds.label,
          data: ds.data,
          borderColor: chartColors[i % chartColors.length],
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: chartColors[i % chartColors.length],
        }))
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 800, easing: 'easeOutQuart' },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            align: 'end',
            labels: {
              color: this.colors.text,
              font: this.defaultFont,
              boxWidth: 8,
              boxHeight: 8,
              borderRadius: 4,
              useBorderRadius: true,
              padding: 16,
            }
          },
          tooltip: this.tooltipConfig(),
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: this.colors.textDim, font: this.defaultFont },
          },
          y: {
            grid: this.gridConfig(),
            ticks: { color: this.colors.textDim, font: this.defaultFont },
            beginAtZero: true,
          }
        }
      }
    });
  },

  // ═══ SET GLOBAL DEFAULTS ═══
  init() {
    Chart.defaults.font.family = "'DM Sans', sans-serif";
    Chart.defaults.font.size = 11;
    Chart.defaults.color = this.colors.textDim;
  }
};

document.addEventListener('DOMContentLoaded', () => MT360Charts.init());
