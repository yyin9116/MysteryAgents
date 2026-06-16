import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import PresetSelector from './PresetSelector';

describe('PresetSelector', () => {
  beforeEach(() => {
    cleanup();
  });

  it('renders all presets', () => {
    render(<PresetSelector onSelect={() => {}} />);
    expect(screen.getAllByText('Quick Match').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Standard').length).toBeGreaterThan(0);
  });

  it('calls onSelect when a preset is clicked', () => {
    const onSelect = vi.fn();
    render(<PresetSelector onSelect={onSelect} />);
    
    fireEvent.click(screen.getAllByText('Quick Match')[0]);
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({
      id: 'quick',
      name: 'Quick Match'
    }));
  });

  it('highlights the selected preset', () => {
    const { rerender } = render(<PresetSelector onSelect={() => {}} selectedId="standard" />);
    
    const standardButton = screen.getAllByText('Standard')[0].closest('button');
    expect(standardButton?.className).toContain('bg-primary/20');
    
    rerender(<PresetSelector onSelect={() => {}} selectedId="hardcore" />);
    const hardcoreButton = screen.getAllByText('Hardcore')[0].closest('button');
    expect(hardcoreButton?.className).toContain('bg-primary/20');
  });
});
