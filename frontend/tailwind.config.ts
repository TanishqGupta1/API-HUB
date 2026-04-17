import type { Config } from "tailwindcss";

const config: Config = {
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
        border: "hsl(var(--border-ui))",
        input: "hsl(var(--input-ui))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
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
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
};

export default config;
