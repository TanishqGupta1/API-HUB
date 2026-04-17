/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Outfit", "sans-serif"],
        mono: ["Fira Code", "monospace"],
      },
      colors: {
        paper: "#f2f0ed",
        "paper-warm": "#ebe8e3",
        vellum: "#f9f7f4",
        ink: "#1e1e24",
        "ink-light": "#484852",
        "ink-muted": "#888894",
        "ink-faint": "#b4b4bc",
        blueprint: "#1e4d92",
        "bp-light": "#2a66be",
        "bp-dark": "#143566",
        "bp-pale": "#eef4fb",
        "bp-ghost": "rgba(30, 77, 146, 0.05)",
        success: "#247a52",
        "success-pale": "#f0f9f4",
        error: "#b93232",
        "error-pale": "#fdf2f2",
        warning: "#c77d2e",
      },
    },
  },
  plugins: [],
};
