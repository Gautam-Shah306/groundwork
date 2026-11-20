import { Card, Eyebrow } from "../ui";
import type { EvalResults } from "../../lib/api";

export interface ConfusionMatrixProps {
  results: EvalResults;
}

export function ConfusionMatrix({ results }: ConfusionMatrixProps) {
  const matrix = results.category_confusion_matrix;
  if (!matrix) return null;

  const trueCategories = Object.keys(matrix).sort();
  // Columns include all categories plus 'no_prediction'
  const colCategories = [...trueCategories, "no_prediction"];

  const perCategory = results.per_category || {};

  return (
    <div className="space-y-6">
      <Card className="p-6 space-y-4">
        <div>
          <Eyebrow>CLASSIFICATION PERFORMANCE</Eyebrow>
          <h3 className="font-display text-[20px] font-normal text-ink">
            Category Confusion Matrix
          </h3>
          <p className="text-[12px] text-muted">
            Rows represent true categories; columns represent predicted categories.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px] border-collapse">
            <thead>
              <tr className="border-b border-border bg-surface-subtle text-muted uppercase font-semibold">
                <th className="p-2.5">True \ Pred</th>
                {colCategories.map((col) => (
                  <th key={col} className="p-2.5 text-center font-mono">
                    {col === "no_prediction" ? "None" : col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trueCategories.map((rowCat) => {
                const rowData = matrix[rowCat] || {};
                return (
                  <tr key={rowCat} className="border-b border-border/50 hover:bg-surface-subtle/50">
                    <td className="p-2.5 font-medium text-ink font-mono">{rowCat}</td>
                    {colCategories.map((colCat) => {
                      const count = rowData[colCat] || 0;
                      const isDiagonal = rowCat === colCat;
                      const isNonZeroOffDiag = !isDiagonal && count > 0;

                      return (
                        <td
                          key={colCat}
                          className={[
                            "p-2.5 text-center font-mono tabular-nums",
                            isDiagonal && count > 0 ? "bg-accent/10 font-bold text-accent" : "",
                            isNonZeroOffDiag ? "bg-warning-soft text-warning font-medium" : "",
                            count === 0 ? "text-muted/40" : "",
                          ]
                            .filter(Boolean)
                            .join(" ")}
                        >
                          {count}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Per-Category Precision, Recall, F1 */}
      <Card className="p-6 space-y-4">
        <div>
          <h3 className="font-display text-[20px] font-normal text-ink">
            Per-Category Metrics
          </h3>
          <p className="text-[12px] text-muted">
            Support, precision, recall, and harmonic F1 score per category.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px] border-collapse">
            <thead>
              <tr className="border-b border-border bg-surface-subtle text-muted text-[11px] uppercase font-semibold">
                <th className="p-2.5">Category</th>
                <th className="p-2.5 text-right">Support</th>
                <th className="p-2.5 text-right">Predicted</th>
                <th className="p-2.5 text-right">Precision</th>
                <th className="p-2.5 text-right">Recall</th>
                <th className="p-2.5 text-right">F1 Score</th>
              </tr>
            </thead>
            <tbody>
              {trueCategories.map((cat) => {
                const row = perCategory[cat] || {
                  support: 0,
                  predicted_count: 0,
                  precision: 0,
                  recall: 0,
                  f1: 0,
                };
                return (
                  <tr key={cat} className="border-b border-border/50 hover:bg-surface-subtle/50 font-mono">
                    <td className="p-2.5 font-medium text-ink">{cat}</td>
                    <td className="p-2.5 text-right tabular-nums text-muted">{row.support}</td>
                    <td className="p-2.5 text-right tabular-nums text-muted">{row.predicted_count}</td>
                    <td className="p-2.5 text-right tabular-nums text-ink">
                      {Math.round(row.precision * 1000) / 10}%
                    </td>
                    <td className="p-2.5 text-right tabular-nums text-ink">
                      {Math.round(row.recall * 1000) / 10}%
                    </td>
                    <td className="p-2.5 text-right tabular-nums font-semibold text-accent">
                      {Math.round(row.f1 * 1000) / 10}%
                    </td>
                  </tr>
                );
              })}
              {/* Macro F1 Row */}
              <tr className="bg-surface-subtle font-semibold">
                <td className="p-2.5 text-ink font-mono" colSpan={5}>
                  Macro-averaged F1 Score (unweighted)
                </td>
                <td className="p-2.5 text-right font-mono tabular-nums text-accent font-bold">
                  {Math.round(results.macro_f1 * 1000) / 10}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
