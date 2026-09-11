import { EmptyState } from "./ui";

// DOM-based bars keep labels and exact values accessible without shipping a
// charting runtime. Bar length always represents the actual API value.
export default function DistributionChart({
  data,
  valueKey = "count",
  unit = "complaints",
  color = "#70a990",
  emptyText = "There’s no data to chart yet.",
}) {
  if (!data?.length)
    return (
      <EmptyState icon="chart" title="No data yet" description={emptyText} />
    );
  const maximum = Math.max(
    ...data.map((item) => Number(item[valueKey]) || 0),
    1,
  );
  return (
    <dl className="space-y-5 p-6">
      {[...data]
        .sort((a, b) => b[valueKey] - a[valueKey])
        .map((item) => (
          <div key={item.category}>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-xs capitalize text-slate-600">
                {item.category.replaceAll("_", " ")}
              </dt>
              <dd className="shrink-0 text-xs font-medium text-slate-700">
                {Number(item[valueKey]).toLocaleString(undefined, {
                  maximumFractionDigits: 2,
                })}{" "}
                <span className="text-[10px] font-normal text-slate-500">
                  {unit}
                </span>
              </dd>
            </div>
            <div
              className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-100"
              aria-hidden="true"
            >
              <div
                className="h-full rounded-full transition-[width] duration-300"
                style={{
                  width: `${(Math.max(0, Number(item[valueKey])) / maximum) * 100}%`,
                  background: color,
                }}
              />
            </div>
          </div>
        ))}
    </dl>
  );
}
