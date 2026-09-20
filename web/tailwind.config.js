/**
 * Design-system tokens: navy #0E2A4D, primary #1663C7, cyan #22D3EE,
 * 8-point spacing grid, and 16/12 px corner radii.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#0E2A4D",
        primary: "#1663C7",
        cyan: "#22D3EE",
      },
      fontFamily: {
        sora: ["Sora", "sans-serif"],
        inter: ["Inter", "sans-serif"],
      },
      borderRadius: {
        lg: "16px",
        md: "12px",
      },
      spacing: {
        // 8-point grid.
        18: "72px",
      },
    },
  },
  plugins: [],
};
