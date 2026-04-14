import React, { useState, useRef } from "react";

export function SearchBar({ onSearch, loading = false, placeholder = "Search any public company globally..." }) {
  const [value, setValue] = useState("");
  const inputRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (value.trim()) onSearch?.(value.trim());
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, width: "100%" }}>
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        disabled={loading}
        style={{
          flex: 1,
          padding: "12px 16px",
          background: "var(--dl-bg-elevated)",
          border: "1px solid var(--dl-border-bright)",
          borderRadius: 8,
          color: "var(--dl-text-primary)",
          fontFamily: "var(--dl-font-sans)",
          fontSize: 14,
          outline: "none",
        }}
      />
      <button
        type="submit"
        disabled={loading || !value.trim()}
        style={{
          padding: "12px 24px",
          background: loading ? "var(--dl-bg-elevated)" : "var(--dl-teal)",
          border: "none",
          borderRadius: 8,
          color: loading ? "var(--dl-text-muted)" : "#000",
          fontWeight: 700,
          fontSize: 13,
          cursor: loading ? "not-allowed" : "pointer",
          whiteSpace: "nowrap",
        }}
      >
        {loading ? "Resolving..." : "Search →"}
      </button>
    </form>
  );
}
