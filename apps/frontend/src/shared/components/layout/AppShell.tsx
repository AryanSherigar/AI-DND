import React, { useState, useCallback, useRef, useEffect } from "react";
import { motion } from "motion/react";
import {
  IconChevronLeft,
  IconChevronRight,
  IconDotsVertical,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconLayoutSidebarRightCollapse,
  IconLayoutSidebarRightExpand,
  IconMenu2,
  IconX,
} from "@tabler/icons-react";
import { AppSidebarContext } from "./appSidebarContext";
import { FloatingNav } from "./FloatingNav";

const K = {
  leftCollapsed: "wevr.sidebar.collapsed",
  leftWidth: "wevr.sidebar.width",
  rightOpen: "wevr.assistant.open",
  rightWidth: "wevr.assistant.width",
};
const RAIL_COLLAPSED = 72;
const RAIL_MIN = 184;
const RAIL_MAX = 420;
const RAIL_DEFAULT = 248;
const PANEL_MIN = 300;
const PANEL_MAX = 520;
const PANEL_DEFAULT = 360;
const SHELL_PAD = 8; // matches md:px-2

const readBool = (key: string, fallback = false): boolean => {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : raw === "1";
  } catch {
    return fallback;
  }
};

const readNum = (key: string, fallback: number, min: number, max: number) => {
  try {
    const raw = Number(localStorage.getItem(key));
    if (Number.isFinite(raw) && raw >= min && raw <= max) return raw;
  } catch {
    // ignore
  }
  return fallback;
};

const persist = (key: string, value: string): void => {
  try {
    localStorage.setItem(key, value);
  } catch {
    // storage unavailable — state stays in-memory only
  }
};

const clamp = (value: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, value));

interface KebabHandleProps {
  onPointerDown: (event: React.PointerEvent) => void;
  active: boolean;
  disabled: boolean;
}

const KebabHandle: React.FC<KebabHandleProps> = ({
  onPointerDown,
  active,
  disabled,
}) => (
  <div
    onPointerDown={onPointerDown}
    className={`group hidden w-4 shrink-0 items-center justify-center md:flex ${
      disabled ? "cursor-default" : "cursor-col-resize"
    }`}
  >
    <IconDotsVertical
      size={16}
      className={`transition-colors ${
        disabled
          ? "text-transparent"
          : active
            ? "text-content"
            : "text-content-faint group-hover:text-content"
      }`}
    />
  </div>
);

export interface AppShellProps {
  /** Navigation rows (SidebarRow / SidebarButton / SidebarDivider). */
  nav: React.ReactNode;
  children: React.ReactNode;
  /** Optional right-hand island (e.g. an assistant panel). */
  rightPanel?: React.ReactNode;
  rightPanelTitle?: string;
  rightPanelSubtitle?: string;
  /** Floating top nav over the content island. Off for surfaces with their own header. */
  showFloatingNav?: boolean;
}

type DragTarget = "left" | "right" | null;

export const AppShell: React.FC<AppShellProps> = ({
  nav,
  children,
  rightPanel,
  rightPanelTitle = "Assistant",
  rightPanelSubtitle,
  showFloatingNav = true,
}) => {
  const hasRight = Boolean(rightPanel);

  const [collapsed, setCollapsed] = useState<boolean>(() =>
    readBool(K.leftCollapsed),
  );
  const [railWidth, setRailWidth] = useState<number>(() =>
    readNum(K.leftWidth, RAIL_DEFAULT, RAIL_MIN, RAIL_MAX),
  );
  const [rightOpen, setRightOpen] = useState<boolean>(() =>
    readBool(K.rightOpen, true),
  );
  const [panelWidth, setPanelWidth] = useState<number>(() =>
    readNum(K.rightWidth, PANEL_DEFAULT, PANEL_MIN, PANEL_MAX),
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [drag, setDrag] = useState<DragTarget>(null);
  const shellRef = useRef<HTMLDivElement>(null);

  const toggleLeft = useCallback(() => {
    setCollapsed((prev) => {
      persist(K.leftCollapsed, prev ? "0" : "1");
      return !prev;
    });
  }, []);

  const toggleRight = useCallback(() => {
    setRightOpen((prev) => {
      persist(K.rightOpen, prev ? "0" : "1");
      return !prev;
    });
  }, []);

  const startDrag = useCallback(
    (target: Exclude<DragTarget, null>) => (event: React.PointerEvent) => {
      if (target === "left" && collapsed) return;
      event.preventDefault();
      setDrag(target);
    },
    [collapsed],
  );

  useEffect(() => {
    if (!drag) return;

    const handleMove = (event: PointerEvent): void => {
      const bounds = shellRef.current?.getBoundingClientRect();
      if (!bounds) return;
      if (drag === "left") {
        setRailWidth(
          clamp(event.clientX - bounds.left - SHELL_PAD, RAIL_MIN, RAIL_MAX),
        );
      } else {
        setPanelWidth(
          clamp(bounds.right - SHELL_PAD - event.clientX, PANEL_MIN, PANEL_MAX),
        );
      }
    };
    const handleUp = (): void => {
      setDrag(null);
      persist(K.leftWidth, String(Math.round(railWidth)));
      persist(K.rightWidth, String(Math.round(panelWidth)));
    };

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drag]);

  const leftWidth = collapsed ? RAIL_COLLAPSED : railWidth;

  return (
    <AppSidebarContext.Provider value={{ collapsed, mobileOpen }}>
      <div
        ref={shellRef}
        className="flex min-h-0 flex-1 flex-col bg-surface-sunken md:flex-row md:gap-0 md:px-2 md:pb-2 md:pt-1.5"
      >
        {/* Mobile top bar */}
        <div className="flex items-center gap-3 border-b border-border-subtle bg-surface-sunken px-4 py-3 md:hidden">
          <button
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
            className="text-content-muted"
          >
            <IconMenu2 size={20} />
          </button>
        </div>

        {/* Left island */}
        <motion.aside
          animate={{ width: leftWidth }}
          transition={
            drag === "left"
              ? { duration: 0 }
              : { type: "spring", stiffness: 260, damping: 30 }
          }
          className="hidden shrink-0 flex-col overflow-hidden rounded-2xl border border-border-strong bg-surface px-3 py-4 md:flex"
        >
          <button
            type="button"
            onClick={toggleLeft}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={`mb-4 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-content-faint transition-colors hover:bg-surface-overlay hover:text-content ${
              collapsed ? "self-center" : "self-end"
            }`}
          >
            {collapsed ? (
              <IconChevronRight size={18} />
            ) : (
              <IconChevronLeft size={18} />
            )}
          </button>
          <nav className="custom-scrollbar flex flex-1 flex-col overflow-y-auto overflow-x-hidden">
            {nav}
          </nav>
        </motion.aside>

        <KebabHandle
          onPointerDown={startDrag("left")}
          active={drag === "left"}
          disabled={collapsed}
        />

        {/* Content island */}
        <div className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-raised md:rounded-2xl md:border md:border-border-strong">
          {showFloatingNav && <FloatingNav />}
          {hasRight && (
            <div className="pointer-events-none absolute right-2.5 top-2.5 z-20 flex gap-1">
              <button
                type="button"
                onClick={toggleLeft}
                aria-label={collapsed ? "Show left panel" : "Hide left panel"}
                className="pointer-events-auto flex h-7 w-7 items-center justify-center rounded-md border border-border-strong bg-surface-overlay/90 text-content-faint backdrop-blur-sm transition-colors hover:text-content"
              >
                {collapsed ? (
                  <IconLayoutSidebarLeftExpand size={15} />
                ) : (
                  <IconLayoutSidebarLeftCollapse size={15} />
                )}
              </button>
              <button
                type="button"
                onClick={toggleRight}
                aria-label={
                  rightOpen ? "Hide assistant panel" : "Show assistant panel"
                }
                className="pointer-events-auto flex h-7 w-7 items-center justify-center rounded-md border border-border-strong bg-surface-overlay/90 text-content-faint backdrop-blur-sm transition-colors hover:text-content"
              >
                {rightOpen ? (
                  <IconLayoutSidebarRightCollapse size={15} />
                ) : (
                  <IconLayoutSidebarRightExpand size={15} />
                )}
              </button>
            </div>
          )}
          {children}
        </div>

        {/* Right island */}
        {hasRight && rightOpen && (
          <>
            <KebabHandle
              onPointerDown={startDrag("right")}
              active={drag === "right"}
              disabled={false}
            />
            <motion.aside
              initial={{ width: panelWidth, opacity: 0 }}
              animate={{ width: panelWidth, opacity: 1 }}
              transition={
                drag === "right"
                  ? { duration: 0 }
                  : { type: "spring", stiffness: 260, damping: 30 }
              }
              className="hidden shrink-0 flex-col overflow-hidden rounded-2xl border border-border-strong bg-surface md:flex"
            >
              <div className="flex items-start justify-between border-b border-border-subtle px-4 py-3">
                <div className="min-w-0">
                  <h3 className="font-mono text-sm font-semibold uppercase tracking-widest text-content">
                    {rightPanelTitle}
                  </h3>
                  {rightPanelSubtitle && (
                    <p className="mt-0.5 font-sans text-xs text-content-faint">
                      {rightPanelSubtitle}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={toggleRight}
                  aria-label="Close assistant panel"
                  className="mt-0.5 shrink-0 text-content-faint transition-colors hover:text-content"
                >
                  <IconX size={18} />
                </button>
              </div>
              <div className="min-h-0 flex-1 overflow-hidden">{rightPanel}</div>
            </motion.aside>
          </>
        )}

      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-[100] md:hidden">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setMobileOpen(false)}
          />
          <motion.aside
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 32 }}
            className="absolute inset-y-0 left-0 flex w-72 flex-col border-r border-border-subtle bg-surface px-3 py-4"
          >
            <div className="mb-7 flex items-center justify-end px-1">
              <button
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="text-content-faint hover:text-content"
              >
                <IconX size={20} />
              </button>
            </div>
            <nav className="flex flex-1 flex-col overflow-y-auto">{nav}</nav>
          </motion.aside>
        </div>
      )}
    </AppSidebarContext.Provider>
  );
};
