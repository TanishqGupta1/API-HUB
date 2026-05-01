"use client";

import { useEffect, useState } from "react";

export interface DimensionInputValue {
  width: number | null;
  height: number | null;
}

interface Props {
  width: number | null;
  height: number | null;
  widthMin: number | null;
  widthMax: number | null;
  heightMin: number | null;
  heightMax: number | null;
  onChange: (value: DimensionInputValue) => void;
}

export function DimensionInput({
  width,
  height,
  widthMin,
  widthMax,
  heightMin,
  heightMax,
  onChange,
}: Props) {
  const [w, setW] = useState<string>(width === null ? "" : String(width));
  const [h, setH] = useState<string>(height === null ? "" : String(height));

  useEffect(() => {
    const wn = w === "" ? null : Number(w);
    const hn = h === "" ? null : Number(h);
    onChange({
      width: Number.isNaN(wn ?? NaN) ? null : wn,
      height: Number.isNaN(hn ?? NaN) ? null : hn,
    });
  }, [w, h, onChange]);

  const wOut =
    w !== "" && widthMin != null && widthMax != null
      ? Number(w) < widthMin || Number(w) > widthMax
      : false;
  const hOut =
    h !== "" && heightMin != null && heightMax != null
      ? Number(h) < heightMin || Number(h) > heightMax
      : false;

  return (
    <div className="grid grid-cols-2 gap-3">
      <label className="flex flex-col gap-1">
        <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
          Width (in)
        </span>
        <input
          aria-label="Width"
          type="number"
          step="0.01"
          min={widthMin ?? undefined}
          max={widthMax ?? undefined}
          value={w}
          onChange={(e) => setW(e.target.value)}
          className="h-9 px-2 text-[13px] border border-[#cfccc8] rounded-md bg-white text-[#1e1e24] focus:outline-none focus:border-[#1e4d92]"
        />
        {wOut ? (
          <span className="text-[10px] text-[#b93232]">
            Width must be between {widthMin} and {widthMax}
          </span>
        ) : null}
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
          Height (in)
        </span>
        <input
          aria-label="Height"
          type="number"
          step="0.01"
          min={heightMin ?? undefined}
          max={heightMax ?? undefined}
          value={h}
          onChange={(e) => setH(e.target.value)}
          className="h-9 px-2 text-[13px] border border-[#cfccc8] rounded-md bg-white text-[#1e1e24] focus:outline-none focus:border-[#1e4d92]"
        />
        {hOut ? (
          <span className="text-[10px] text-[#b93232]">
            Height must be between {heightMin} and {heightMax}
          </span>
        ) : null}
      </label>
    </div>
  );
}
