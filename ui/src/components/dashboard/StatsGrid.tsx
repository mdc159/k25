/**
 * StatsGrid Component
 *
 * Archon-style stat pills showing pipeline overview:
 * - Workers online/total
 * - Jobs queued
 * - Jobs processing
 * - Jobs completed
 *
 * Features glassmorphism styling with color-coded glows.
 */

import React from 'react';
import { Users, Clock, Zap, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DashboardStats } from '@/types/dashboard';

interface StatsGridProps {
  stats: DashboardStats;
  className?: string;
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  subtext?: string;
  colorScheme: 'green' | 'pink' | 'cyan' | 'emerald';
}

const COLOR_SCHEMES = {
  green: {
    border: 'border-green-500/50',
    glow: 'shadow-[0_0_20px_5px_rgba(34,197,94,0.15)]',
    iconBg: 'bg-green-500/20',
    iconText: 'text-green-400',
    valueText: 'text-green-300',
  },
  pink: {
    border: 'border-pink-500/50',
    glow: 'shadow-[0_0_20px_5px_rgba(236,72,153,0.15)]',
    iconBg: 'bg-pink-500/20',
    iconText: 'text-pink-400',
    valueText: 'text-pink-300',
  },
  cyan: {
    border: 'border-cyan-500/50',
    glow: 'shadow-[0_0_20px_5px_rgba(6,182,212,0.15)]',
    iconBg: 'bg-cyan-500/20',
    iconText: 'text-cyan-400',
    valueText: 'text-cyan-300',
  },
  emerald: {
    border: 'border-emerald-500/50',
    glow: 'shadow-[0_0_20px_5px_rgba(16,185,129,0.15)]',
    iconBg: 'bg-emerald-500/20',
    iconText: 'text-emerald-400',
    valueText: 'text-emerald-300',
  },
};

function StatCard({ icon, label, value, subtext, colorScheme }: StatCardProps) {
  const colors = COLOR_SCHEMES[colorScheme];

  return (
    <div
      className={cn(
        // Glassmorphism base
        'rounded-lg border backdrop-blur-md',
        'bg-white/5 border-white/10',
        'shadow-lg shadow-black/20',
        // Color-specific glow
        colors.border,
        colors.glow,
        // Layout
        'p-4 flex items-center gap-3',
        // Transitions
        'transition-all duration-300 hover:scale-[1.02]'
      )}
    >
      {/* Icon */}
      <div
        className={cn(
          'h-10 w-10 rounded-full flex items-center justify-center',
          colors.iconBg,
          colors.iconText
        )}
      >
        {icon}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-xs text-zinc-500 uppercase tracking-wide">{label}</p>
        <p className={cn('text-2xl font-bold', colors.valueText)}>{value}</p>
        {subtext && (
          <p className="text-xs text-zinc-600">{subtext}</p>
        )}
      </div>
    </div>
  );
}

export function StatsGrid({ stats, className }: StatsGridProps) {
  return (
    <div className={cn('grid grid-cols-2 lg:grid-cols-4 gap-3', className)}>
      <StatCard
        icon={<Users className="h-5 w-5" />}
        label="Workers"
        value={`${stats.workers.online}/${stats.workers.total}`}
        subtext="online"
        colorScheme="green"
      />

      <StatCard
        icon={<Clock className="h-5 w-5" />}
        label="Queued"
        value={stats.queued}
        subtext="waiting"
        colorScheme="pink"
      />

      <StatCard
        icon={<Zap className="h-5 w-5" />}
        label="Processing"
        value={stats.processing}
        subtext="active"
        colorScheme="cyan"
      />

      <StatCard
        icon={<CheckCircle className="h-5 w-5" />}
        label="Completed"
        value={stats.completed}
        subtext="total"
        colorScheme="emerald"
      />
    </div>
  );
}
