const brl0 = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const brlCompact = new Intl.NumberFormat("pt-BR", {
  style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1,
});
const num0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const num1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export const brl = (v: number | null | undefined) => (v == null ? "—" : brl0.format(v));
export const brlShort = (v: number | null | undefined) => (v == null ? "—" : brlCompact.format(v));
export const num = (v: number | null | undefined) => (v == null ? "—" : num0.format(v));
export const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? "—" : `${(v * 100).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
export const pp = (v: number | null | undefined) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${num1.format(v * 100)} p.p.`;
export const signedPct = (v: number | null | undefined) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${num1.format(v * 100)}%`;
export const signedBrl = (v: number | null | undefined) =>
  v == null ? "—" : `${v >= 0 ? "+" : "−"}${brl0.format(Math.abs(v))}`;
export const hours = (v: number | null | undefined) => (v == null ? "—" : `${num0.format(v)} h`);
export const dateBR = (v: string | null | undefined) =>
  v ? new Date(`${v.slice(0, 10)}T12:00:00`).toLocaleDateString("pt-BR") : "—";

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
export const monthLabel = (ym: string) => {
  const [y, m] = ym.split("-");
  return `${MONTHS[Number(m) - 1]}/${y.slice(2)}`;
};
