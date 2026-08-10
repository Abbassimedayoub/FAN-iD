/**
 * Tokens du design system validé [CADR] (§4.3 Source B) : navy #0E2A4D,
 * primary #1663C7, cyan #22D3EE, grille 8pt, rayons 16/12.
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
        // grille 8pt
        18: "72px",
      },
    },
  },
  plugins: [],
};
