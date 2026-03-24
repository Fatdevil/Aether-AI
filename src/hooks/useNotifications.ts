/**
 * useNotifications - Polls for critical sentinel alerts and shows browser notifications.
 * Requests Notification API permission on first load.
 */
import { useEffect, useRef, useCallback } from 'react';

const POLL_INTERVAL = 60_000; // Check every 60 seconds
const MIN_IMPACT = 8; // Only notify on impact >= 8

interface Alert {
  title: string;
  impact_score: number;
  category: string;
  one_liner: string;
  urgency: string;
  timestamp: string;
}

export function useNotifications() {
  const seenAlerts = useRef<Set<string>>(new Set());
  const permissionGranted = useRef(false);

  // Request notification permission on mount
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().then(perm => {
        permissionGranted.current = perm === 'granted';
      });
    } else if ('Notification' in window) {
      permissionGranted.current = Notification.permission === 'granted';
    }
  }, []);

  const showNotification = useCallback((alert: Alert) => {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;

    const urgencyEmoji = alert.urgency === 'critical' ? '🚨' : alert.urgency === 'urgent' ? '⚠️' : '📊';
    const notification = new Notification(`${urgencyEmoji} Aether AI Alert`, {
      body: `${alert.one_liner}\n\nImpact: ${alert.impact_score}/10 · ${alert.category}`,
      icon: '/vite.svg',
      tag: alert.title, // Prevents duplicates
      requireInteraction: alert.impact_score >= 9,
    });

    notification.onclick = () => {
      window.focus();
      notification.close();
    };

    // Auto-close after 15 seconds (unless critical)
    if (alert.impact_score < 9) {
      setTimeout(() => notification.close(), 15_000);
    }
  }, []);

  // Poll for alerts
  useEffect(() => {
    const checkAlerts = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/alerts?min_impact=${MIN_IMPACT}`);
        const data = await res.json();
        const alerts: Alert[] = data.alerts || [];

        for (const alert of alerts) {
          const key = `${alert.title}_${alert.timestamp}`;
          if (!seenAlerts.current.has(key)) {
            seenAlerts.current.add(key);
            showNotification(alert);
          }
        }
      } catch {
        // Silently fail - notifications are best-effort
      }
    };

    checkAlerts(); // Check immediately
    const interval = setInterval(checkAlerts, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [showNotification]);
}
