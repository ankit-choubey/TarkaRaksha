"use client";

import React, { useEffect } from "react";
import { X } from "lucide-react";

interface DrawerContainerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  badge?: string;
  badgeType?: "pass" | "drift" | "unknown" | "neutral";
  children: React.ReactNode;
}

export const DrawerContainer: React.FC<DrawerContainerProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  badge,
  badgeType = "neutral",
  children,
}) => {
  // ESC key listener to close drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const getBadgeClass = () => {
    switch (badgeType) {
      case "pass":
        return "bg-emerald-50 text-emerald-800 border-emerald-200";
      case "drift":
        return "bg-rose-50 text-rose-800 border-rose-200";
      case "unknown":
        return "bg-amber-50 text-amber-800 border-amber-200";
      case "neutral":
      default:
        return "bg-neutral-100 text-neutral-800 border-neutral-200";
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity duration-300"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-over Drawer Panel */}
      <div className="fixed inset-y-0 right-0 flex max-w-full pl-6 sm:pl-10">
        <div className="w-screen max-w-2xl transform bg-white shadow-2xl transition-transform duration-300 ease-out border-l border-neutral-200 flex flex-col">
          {/* Header */}
          <div className="px-6 py-5 border-b border-neutral-200 bg-neutral-50/70 flex items-start justify-between">
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold tracking-tight text-neutral-900">{title}</h2>
                {badge && (
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-mono font-semibold border ${getBadgeClass()}`}
                  >
                    {badge}
                  </span>
                )}
              </div>
              {subtitle && <p className="text-xs text-neutral-500 font-medium">{subtitle}</p>}
            </div>

            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-neutral-400 hover:text-neutral-700 hover:bg-neutral-200/50 transition"
              aria-label="Close drawer"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Scrollable Content Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">{children}</div>

          {/* Footer with Close button */}
          <div className="px-6 py-3.5 border-t border-neutral-200 bg-neutral-50 flex items-center justify-between text-xs text-neutral-500">
            <span className="font-mono text-[11px]">Press ESC to dismiss</span>
            <button
              onClick={onClose}
              className="rounded-lg bg-white px-3 py-1.5 font-semibold text-neutral-700 border border-neutral-300 hover:bg-neutral-50 active:scale-[0.98] transition shadow-2xs"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
