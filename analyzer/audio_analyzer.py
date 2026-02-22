"""
DJ Track Analyzer - Core Audio Analysis Engine
Analyzes audio files for BPM, key, energy level, and generates waveforms
"""

import librosa
import numpy as np
from mutagen import File as MutagenFile
from pathlib import Path
import json


class AudioAnalyzer:
    """Main audio analysis class for DJ tracks"""

    def __init__(self, fast_mode=True):
        self.sample_rate = 22050  # librosa default, good for music analysis
        self.fast_mode = fast_mode  # Skip waveform generation for speed

    def analyze_track(self, file_path):
        """
        Analyze a single track and return all metrics

        Args:
            file_path: Path to audio file (MP3, WAV, FLAC, etc.)

        Returns:
            dict: Analysis results including BPM, key, energy, metadata, etc.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Track not found: {file_path}")

        print(f"Analyzing: {file_path.name}")

        # Load audio file
        y, sr = librosa.load(str(file_path), sr=self.sample_rate)

        # Perform all analyses
        results = {
            'file_path': str(file_path.absolute()),
            'filename': file_path.name,
            'bpm': self._detect_bpm(y, sr),
            'key': self._detect_key(y, sr),
            'energy': self._calculate_energy(y),
            'metadata': self._extract_metadata(file_path),
            'audio_info': self._get_audio_info(file_path, y, sr),
            'duration': len(y) / sr  # Duration in seconds
        }

        # Skip waveform in fast mode (generated separately in UI)
        if not self.fast_mode:
            results['waveform'] = self._generate_waveform(y, sr)

        print(f"[OK] Analysis complete: {results['bpm']} BPM, {results['key']['notation']} ({results['key']['camelot']})")

        return results

    def _detect_bpm(self, y, sr):
        """Detect BPM using librosa's beat tracking"""
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            # In librosa 0.10+, tempo can be a scalar or array
            if isinstance(tempo, np.ndarray):
                if tempo.size == 0:
                    return None
                bpm = float(tempo[0]) if tempo.size > 0 else float(tempo)
            else:
                bpm = float(tempo)
            return round(bpm, 1)
        except Exception as e:
            print(f"Warning: BPM detection failed - {e}")
            return None

    def _detect_key(self, y, sr):
        """
        Detect musical key using chroma features
        Returns key in multiple notations (musical, Camelot, Open Key)
        """
        try:
            # Use chroma_cqt for better key detection
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

            # Average chroma across time
            chroma_avg = np.mean(chroma, axis=1)

            # Find the dominant pitch class
            key_index = np.argmax(chroma_avg)

            # Determine if major or minor based on chroma pattern
            # This is a simplified approach
            is_major = self._is_major_key(chroma_avg)

            # Convert to key notation
            key_notation = self._index_to_key(key_index, is_major)

            # Convert to Camelot notation
            camelot = self._to_camelot(key_index, is_major)

            # Convert to Open Key notation
            open_key = self._to_open_key(key_index, is_major)

            return {
                'notation': key_notation,      # e.g., "C Major"
                'camelot': camelot,            # e.g., "8B"
                'open_key': open_key,          # e.g., "1d"
                'confidence': 'medium'         # Placeholder for now
            }
        except Exception as e:
            print(f"Warning: Key detection failed - {e}")
            return {
                'notation': 'Unknown',
                'camelot': 'N/A',
                'open_key': 'N/A',
                'confidence': 'none'
            }

    def _is_major_key(self, chroma_avg):
        """
        Determine if key is major or minor based on chroma pattern
        Major keys have stronger 3rd and 7th scale degrees
        """
        # This is simplified - a proper implementation would use
        # key profiles (Krumhansl-Schmuckler algorithm)
        major_profile = np.array([1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1])
        minor_profile = np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0])

        # Normalize chroma
        chroma_norm = chroma_avg / (np.sum(chroma_avg) + 1e-8)

        # Correlate with profiles
        major_corr = np.corrcoef(chroma_norm, major_profile)[0, 1]
        minor_corr = np.corrcoef(chroma_norm, minor_profile)[0, 1]

        return major_corr > minor_corr

    def _index_to_key(self, key_index, is_major):
        """Convert pitch class index to key notation"""
        keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        key_name = keys[key_index]
        return f"{key_name} {'Major' if is_major else 'Minor'}"

    def _to_camelot(self, key_index, is_major):
        """
        Convert to Camelot notation (used by Rekordbox, Traktor)
        Camelot Wheel: 1A-12A (minor), 1B-12B (major)
        """
        # Camelot mapping
        camelot_major = ['8B', '3B', '10B', '5B', '12B', '7B', '2B', '9B', '4B', '11B', '6B', '1B']
        camelot_minor = ['5A', '12A', '7A', '2A', '9A', '4A', '11A', '6A', '1A', '8A', '3A', '10A']

        if is_major:
            return camelot_major[key_index]
        else:
            return camelot_minor[key_index]

    def _to_open_key(self, key_index, is_major):
        """
        Convert to Open Key notation (alternative to Camelot)
        Open Key: 1d-12d (minor), 1m-12m (major)
        """
        # Open Key uses numbers 1-12 with d (minor) or m (major)
        open_key_numbers = [1, 8, 3, 10, 5, 12, 7, 2, 9, 4, 11, 6]
        number = open_key_numbers[key_index]
        return f"{number}{'m' if is_major else 'd'}"

    def _calculate_energy(self, y):
        """
        Calculate energy level (1-10 scale) based on RMS
        Higher RMS = more energy
        """
        try:
            # Calculate RMS energy
            rms = librosa.feature.rms(y=y)[0]

            # Average RMS across the track
            avg_rms = np.mean(rms)

            # Normalize to 1-10 scale (empirically determined thresholds)
            # These thresholds work well for most electronic music
            if avg_rms < 0.05:
                energy = 1
            elif avg_rms < 0.08:
                energy = 2
            elif avg_rms < 0.11:
                energy = 3
            elif avg_rms < 0.14:
                energy = 4
            elif avg_rms < 0.17:
                energy = 5
            elif avg_rms < 0.20:
                energy = 6
            elif avg_rms < 0.23:
                energy = 7
            elif avg_rms < 0.26:
                energy = 8
            elif avg_rms < 0.30:
                energy = 9
            else:
                energy = 10

            return {
                'level': energy,
                'rms': float(avg_rms),
                'description': self._energy_description(energy)
            }
        except Exception as e:
            print(f"Warning: Energy calculation failed - {e}")
            return {
                'level': 5,
                'rms': 0.0,
                'description': 'Unknown'
            }

    def _energy_description(self, energy_level):
        """Convert energy level to description"""
        descriptions = {
            1: 'Very Low',
            2: 'Low',
            3: 'Low-Medium',
            4: 'Medium',
            5: 'Medium',
            6: 'Medium-High',
            7: 'High',
            8: 'High',
            9: 'Very High',
            10: 'Peak Energy'
        }
        return descriptions.get(energy_level, 'Unknown')

    def _generate_waveform(self, y, sr, num_points=2000):
        """
        Generate waveform data for visualization
        Downsamples audio to num_points for efficient display
        """
        try:
            # Downsample to num_points for visualization
            step = len(y) // num_points
            if step < 1:
                step = 1

            waveform = y[::step]

            # Normalize to -1 to 1 range
            if len(waveform) > 0:
                waveform = waveform / (np.max(np.abs(waveform)) + 1e-8)

            # Convert to list for JSON serialization
            return waveform.tolist()
        except Exception as e:
            print(f"Warning: Waveform generation failed - {e}")
            return []

    def _extract_metadata(self, file_path):
        """Extract ID3 tags and metadata using mutagen"""
        try:
            audio = MutagenFile(str(file_path))

            if audio is None:
                return self._default_metadata()

            # Extract common tags (works for MP3, FLAC, M4A, etc.)
            metadata = {
                'artist': self._get_tag(audio, ['artist', 'TPE1', '\xa9ART']),
                'title': self._get_tag(audio, ['title', 'TIT2', '\xa9nam']),
                'album': self._get_tag(audio, ['album', 'TALB', '\xa9alb']),
                'genre': self._get_tag(audio, ['genre', 'TCON', '\xa9gen']),
                'year': self._get_tag(audio, ['date', 'TDRC', '\xa9day']),
                'comment': self._get_tag(audio, ['comment', 'COMM', '\xa9cmt'])
            }

            return metadata
        except Exception as e:
            print(f"Warning: Metadata extraction failed - {e}")
            return self._default_metadata()

    def _get_tag(self, audio, tag_names):
        """Get tag value from multiple possible tag names"""
        for tag in tag_names:
            if tag in audio:
                value = audio[tag]
                # Handle different tag formats
                if isinstance(value, list):
                    return str(value[0]) if value else ''
                return str(value)
        return ''

    def _default_metadata(self):
        """Return default metadata structure"""
        return {
            'artist': '',
            'title': '',
            'album': '',
            'genre': '',
            'year': '',
            'comment': ''
        }

    def _get_audio_info(self, file_path, y, sr):
        """Get audio file technical information"""
        try:
            audio = MutagenFile(str(file_path))

            if audio is None:
                return self._default_audio_info(file_path, y, sr)

            # Get bitrate, sample rate, format
            bitrate = getattr(audio.info, 'bitrate', 0) // 1000  # Convert to kbps
            sample_rate = getattr(audio.info, 'sample_rate', sr)
            channels = getattr(audio.info, 'channels', 0)

            # Determine format from file extension
            format_name = file_path.suffix.upper().replace('.', '')

            # File size
            file_size_mb = file_path.stat().st_size / (1024 * 1024)

            return {
                'format': format_name,
                'bitrate': bitrate,
                'sample_rate': sample_rate,
                'channels': channels,
                'file_size_mb': round(file_size_mb, 2)
            }
        except Exception as e:
            print(f"Warning: Audio info extraction failed - {e}")
            return self._default_audio_info(file_path, y, sr)

    def _default_audio_info(self, file_path, y, sr):
        """Return default audio info"""
        format_name = file_path.suffix.upper().replace('.', '')
        file_size_mb = file_path.stat().st_size / (1024 * 1024)

        return {
            'format': format_name,
            'bitrate': 0,
            'sample_rate': sr,
            'channels': 0,
            'file_size_mb': round(file_size_mb, 2)
        }

    def save_analysis(self, results, output_path=None):
        """Save analysis results to JSON file"""
        if output_path is None:
            # Create output filename based on input
            input_path = Path(results['file_path'])
            output_path = input_path.with_suffix('.analysis.json')

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"Analysis saved to: {output_path}")
        return output_path


# Quick test function
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python audio_analyzer.py <path_to_audio_file>")
        sys.exit(1)

    analyzer = AudioAnalyzer()
    results = analyzer.analyze_track(sys.argv[1])

    # Print results
    print("\n" + "="*60)
    print("ANALYSIS RESULTS")
    print("="*60)
    print(f"File: {results['filename']}")
    print(f"BPM: {results['bpm']}")
    print(f"Key: {results['key']['notation']} | Camelot: {results['key']['camelot']} | Open Key: {results['key']['open_key']}")
    print(f"Energy: {results['energy']['level']}/10 ({results['energy']['description']})")
    print(f"Duration: {results['duration']:.1f} seconds")
    print(f"\nMetadata:")
    print(f"  Artist: {results['metadata']['artist']}")
    print(f"  Title: {results['metadata']['title']}")
    print(f"  Genre: {results['metadata']['genre']}")
    print(f"\nAudio Info:")
    print(f"  Format: {results['audio_info']['format']}")
    print(f"  Bitrate: {results['audio_info']['bitrate']} kbps")
    print(f"  Sample Rate: {results['audio_info']['sample_rate']} Hz")
    print(f"  File Size: {results['audio_info']['file_size_mb']} MB")
    print("="*60)

    # Save to JSON
    analyzer.save_analysis(results)
