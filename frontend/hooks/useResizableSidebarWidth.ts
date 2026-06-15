"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "mm-sidebar-width";
const DEFAULT_WIDTH = 420;
const MIN_WIDTH = 320;
const MAX_WIDTH_RATIO = 0.7;
const KEYBOARD_STEP = 20;

function clampWidth(width: number): number {
  const max = typeof window !== "undefined" ? window.innerWidth * MAX_WIDTH_RATIO : 900;
  return Math.min(max, Math.max(MIN_WIDTH, width));
}

function readStoredWidth(): number {
  if (typeof window === "undefined") return DEFAULT_WIDTH;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_WIDTH;
    const parsed = Number.parseInt(raw, 10);
    return Number.isFinite(parsed) ? clampWidth(parsed) : DEFAULT_WIDTH;
  } catch {
    return DEFAULT_WIDTH;
  }
}

export function useResizableSidebarWidth() {
  const [width, setWidthState] = useState(() => readStoredWidth());
  const [isDragging, setIsDragging] = useState(false);
  const widthRef = useRef(width);

  useEffect(() => {
    widthRef.current = width;
  }, [width]);

  const persistWidth = useCallback((next: number) => {
    const clamped = clampWidth(next);
    widthRef.current = clamped;
    setWidthState(clamped);
    try {
      localStorage.setItem(STORAGE_KEY, String(Math.round(clamped)));
    } catch {
      /* ignore quota errors */
    }
  }, []);

  const resetWidth = useCallback(() => {
    persistWidth(DEFAULT_WIDTH);
  }, [persistWidth]);

  const nudgeWidth = useCallback(
    (delta: number) => {
      persistWidth(widthRef.current + delta);
    },
    [persistWidth]
  );

  const startDrag = useCallback(
    (clientX: number) => {
      setIsDragging(true);
      const startX = clientX;
      const startWidth = widthRef.current;

      const onMove = (event: PointerEvent) => {
        const delta = startX - event.clientX;
        persistWidth(startWidth + delta);
      };

      const onUp = () => {
        setIsDragging(false);
        document.body.style.removeProperty("user-select");
        document.body.style.removeProperty("cursor");
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };

      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [persistWidth]
  );

  useEffect(() => {
    const onResize = () => {
      persistWidth(widthRef.current);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [persistWidth]);

  return {
    width,
    isDragging,
    startDrag,
    resetWidth,
    nudgeWidth,
    minWidth: MIN_WIDTH,
    keyboardStep: KEYBOARD_STEP,
  };
}
