export default function HomeSection({ title, children }) {
  return (
    <section className="home-section">
      <h2 className="home-section-title">{title}</h2>
      {children}
    </section>
  );
}
