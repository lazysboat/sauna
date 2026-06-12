/* Deterministic per-experience color (SPEC §7f).
 * 8-entry warm palette: olive, terracotta, gold, sage, walnut, moss, sienna,
 * stone. The original repo's exact RGBs weren't available — these are derived
 * from the Traverum tokens (same hues, tints hand-picked to stay on-brand). */

export type ExperienceColor = {
  bgSolid: string;
  bgGhost: string;
  border: string;
  textSolid: string;
  textGhost: string;
  dot: string;
};

const PALETTE: ExperienceColor[] = [
  { // olive
    bgSolid: "#e2e7db", bgGhost: "#f2f4ee", border: "#5a6b4e",
    textSolid: "#3c4933", textGhost: "#6f7d63", dot: "#5a6b4e",
  },
  { // terracotta
    bgSolid: "#f0e1d8", bgGhost: "#f8f1ec", border: "#b8866b",
    textSolid: "#7d5340", textGhost: "#a5836f", dot: "#b8866b",
  },
  { // gold
    bgSolid: "#f1e8d4", bgGhost: "#f9f5ea", border: "#c9a961",
    textSolid: "#82682f", textGhost: "#a8915c", dot: "#c9a961",
  },
  { // sage
    bgSolid: "#e0eae0", bgGhost: "#f0f5f0", border: "#6b8e6b",
    textSolid: "#42603f", textGhost: "#6e8a6c", dot: "#6b8e6b",
  },
  { // walnut
    bgSolid: "#e8ded4", bgGhost: "#f5f0ea", border: "#5d4631",
    textSolid: "#4a3623", textGhost: "#7d6750", dot: "#5d4631",
  },
  { // moss
    bgSolid: "#e6e8da", bgGhost: "#f3f4ec", border: "#7a8463",
    textSolid: "#4e5640", textGhost: "#78816a", dot: "#7a8463",
  },
  { // sienna
    bgSolid: "#eeded2", bgGhost: "#f7efe9", border: "#9c6644",
    textSolid: "#6d4327", textGhost: "#97714f", dot: "#9c6644",
  },
  { // stone
    bgSolid: "#e7e4de", bgGhost: "#f3f2ee", border: "#8a8378",
    textSolid: "#56514a", textGhost: "#807a71", dot: "#8a8378",
  },
];

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

// Neutral fallback for sessions whose experience is missing (SPEC §4)
export const NEUTRAL_COLOR: ExperienceColor = PALETTE[7];

export function getExperienceColor(id: string): ExperienceColor {
  return PALETTE[hashString(id) % PALETTE.length];
}
