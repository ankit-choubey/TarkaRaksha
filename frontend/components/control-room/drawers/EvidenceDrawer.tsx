"use client";

import React, { useState } from "react";
import { DrawerContainer } from "./DrawerContainer";
import { ControlRoomSnapshot } from "../../../lib/types";
import { formatTimestamp } from "../../../lib/formatters";
import { FileCheck2, Code, Copy, Check } from "lucide-react";

interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot: ControlRoomSnapshot;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  isOpen,
  onClose,
  snapshot,
}) => {
  const [viewMode, setViewMode] = useState<"table" | "json">("table");
  const [copied, setCopied] = useState(false);
  const records = snapshot.evidence_records;

  const copyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(records, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getAuthorityBadge = (auth: string) => {
    switch (auth) {
      case "AUTHORITATIVE":
        return "bg-emerald-50 text-emerald-800 border-emerald-200";
      case "PROVIDER":
        return "bg-blue-50 text-blue-800 border-blue-200";
      case "MERCHANT_ATTESTED":
        return "bg-neutral-100 text-neutral-800 border-neutral-300";
      case "ADVISORY":
      default:
        return "bg-violet-50 text-violet-800 border-violet-200";
    }
  };

  return (
    <DrawerContainer
      isOpen={isOpen}
      onClose={onClose}
      title="Evidence Bundle & Provenance"
      subtitle="Auditable immutable records from Intent, Agents, Gateway, and Verification Engines"
      badge={`${records.length} RECORDS`}
      badgeType="neutral"
    >
      {/* View Toggle */}
      <div className="flex items-center justify-between border-b border-neutral-200 pb-3">
        <div className="flex items-center space-x-2 text-xs">
          <button
            onClick={() => setViewMode("table")}
            className={`rounded-lg px-2.5 py-1 font-medium transition ${
              viewMode === "table"
                ? "bg-neutral-900 text-white"
                : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
            }`}
          >
            Human Table
          </button>
          <button
            onClick={() => setViewMode("json")}
            className={`rounded-lg px-2.5 py-1 font-medium transition ${
              viewMode === "json"
                ? "bg-neutral-900 text-white"
                : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
            }`}
          >
            Raw JSON
          </button>
        </div>

        {viewMode === "json" && (
          <button
            onClick={copyJson}
            className="inline-flex items-center space-x-1 text-xs text-neutral-500 hover:text-neutral-900"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copied ? "Copied" : "Copy JSON"}</span>
          </button>
        )}
      </div>

      {viewMode === "table" ? (
        <div className="rounded-xl border border-neutral-200 overflow-hidden text-xs">
          <table className="min-w-full divide-y divide-neutral-200 text-left">
            <thead className="bg-neutral-50 text-[10px] uppercase font-mono text-neutral-400">
              <tr>
                <th className="px-3 py-2.5">Source & Authority</th>
                <th className="px-3 py-2.5">Field</th>
                <th className="px-3 py-2.5">Value Repr</th>
                <th className="px-3 py-2.5 text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100 font-mono text-xs">
              {records.map((item) => (
                <tr key={item.evidence_id} className="hover:bg-neutral-50/50">
                  <td className="px-3 py-2.5">
                    <div className="font-semibold text-neutral-900">{item.source}</div>
                    <span
                      className={`inline-block mt-0.5 rounded px-1.5 py-0.2 text-[9px] font-mono border ${getAuthorityBadge(
                        item.authority
                      )}`}
                    >
                      {item.authority}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-neutral-600 font-semibold">{item.field_name}</td>
                  <td className="px-3 py-2.5 text-neutral-900 max-w-[200px] truncate" title={item.field_value_repr}>
                    {item.field_value_repr}
                  </td>
                  <td className="px-3 py-2.5 text-right text-neutral-400 text-[11px]">
                    {formatTimestamp(item.recorded_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <pre className="rounded-xl bg-neutral-900 text-neutral-300 p-4 font-mono text-xs overflow-x-auto border border-neutral-800 max-h-[500px]">
          {JSON.stringify(records, null, 2)}
        </pre>
      )}
    </DrawerContainer>
  );
};
