export const styles = {
  section: {
    container: "mb-8",
    spacing: "space-y-8",
    contentSpacing: "space-y-4",
    contentSpacingTight: "space-y-1", // Used in YouTube for tighter transcript segments
  },
  headers: {
    h1: "text-3xl font-bold text-slate-900 mb-6",
    h2: "text-2xl font-semibold text-slate-900 mb-4",
  },
  content: {
    text: "text-slate-700",
    list: {
      ul: "list-disc pl-6 space-y-2 text-slate-700",
      ol: "list-decimal pl-6 space-y-2 text-slate-700",
    },
    table: {
      wrapper: "overflow-x-auto",
      table: "min-w-full divide-y divide-slate-200",
      cell: "px-4 py-2 text-sm text-slate-700"
    }
  }
} as const; 