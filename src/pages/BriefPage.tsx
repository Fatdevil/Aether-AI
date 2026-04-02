import DailyBrief from '../components/DailyBrief';

export default function BriefPage() {
  return (
    <main className="container" style={{ paddingBottom: '80px' }}>
      <h2 style={{ fontSize: '1.5rem', fontWeight: 800, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        📰 Dagens Rapporter
      </h2>
      <p style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem', marginBottom: '2rem' }}>
        Här hittar du de senaste sammanfattningarna och marknadsbreven från Aether AI Chief Investment Officer (Opus 4.6).
      </p>
      
      <DailyBrief />
      
      <div className="glass-panel" style={{ marginTop: '2rem', padding: '1.5rem', textAlign: 'center', opacity: 0.7 }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
          Opus 4.6 genererar ett morgonbrev kl 08:00 och en eftermiddagsuppdatering kl 14:30 varje börsdag.
        </p>
      </div>
    </main>
  );
}
