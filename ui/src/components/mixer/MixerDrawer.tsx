import React from 'react';
import { useStore } from '@/stores/useStore';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription
} from '@/components/ui/sheet';
import { Slider } from '@/components/ui/slider';
import { Button } from '@/components/ui/button';
import { RotateCcw } from 'lucide-react';
import { audioManager, StemAudioManager } from '@/lib/audio';
import type { StemId } from '@/types/karaoke';

export const MixerDrawer: React.FC = () => {
  const { activeDrawer, setActiveDrawer, stemGains, setStemGain } = useStore();
  const isOpen = activeDrawer === 'mixer';

  const stems = Object.keys(stemGains) as StemId[];

  // Update both store and audio engine
  const handleGainChange = (stem: StemId, dbValue: number) => {
    setStemGain(stem, dbValue);
    const linearGain = StemAudioManager.dbToLinear(dbValue);
    audioManager.setGain(stem, linearGain);
  };

  const handleReset = () => {
    stems.forEach(stem => {
      setStemGain(stem, 0);
      audioManager.setGain(stem, 1.0); // 0 dB = 1.0 linear
    });
  };

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && setActiveDrawer('none')}>
      <SheetContent side="right" className="w-[300px] sm:w-[400px] border-l-zinc-800 bg-zinc-950/90 backdrop-blur-md text-zinc-100">
        <SheetHeader className="mb-8">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-zinc-100">Mixer</SheetTitle>
            <Button variant="ghost" size="icon" onClick={handleReset} title="Reset all">
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
          <SheetDescription className="text-zinc-500">
            Adjust stem volumes in real-time.
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-8">
          {stems.map(stem => (
            <div key={stem} className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="capitalize font-medium text-zinc-300">{stem}</span>
                <span className="text-zinc-500 font-mono text-xs">
                  {stemGains[stem].toFixed(1)} dB
                </span>
              </div>
              <Slider
                value={[stemGains[stem]]}
                min={-12}
                max={6}
                step={0.5}
                onValueChange={(vals) => handleGainChange(stem, vals[0])}
                className="[&_.bg-primary]:bg-zinc-100 [&_.border-primary]:border-zinc-100"
              />
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
};
