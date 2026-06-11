export default function StatCard({ label, value }) {
  return (
    <div className="panel home-stat-card">
      <div className="home-stat-label">{label}</div>
      <div className="home-stat-value">{value}</div>
    </div>
  );
}
