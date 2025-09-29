from pathlib import Path
import demucs.separate
from log import get_logger, suppress_stdout_stderr
from enum import Enum

logger = get_logger(__name__)

class Models(Enum):
    HTDEMUCS = "htdemucs"
    HTDEMUCS_FT = "htdemucs_ft"


def extract_stems(input_file: Path, output_dir: Path, model: Models = Models.HTDEMUCS) -> dict[str, Path]:

    logger.info(f"Extracting stems from {input_file} to {output_dir} using model {model.value}")
    
    with suppress_stdout_stderr():
        demucs.separate.main([
            "-n", model.value,
            "-o", str(output_dir),
            str(input_file)
        ])

    base_dir = output_dir / model.value / input_file.stem
    ext = input_file.suffix

    res = {
        'vocals': base_dir / f'vocals{ext}',
        'drums': base_dir / f'drums{ext}',
        'bass': base_dir / f'bass{ext}',
        'other': base_dir / f'other{ext}'
    }
    logger.info(f"Extracted stems: {res}")
    return res

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python extract.py <input_wav_file> <output_dir>")
        sys.exit(1)
    input_wav = Path(sys.argv[1])
    output_directory = Path(sys.argv[2])
    stems = extract_stems(input_wav, output_directory)
    print("Extracted stems:")
    for stem, path in stems.items():
        print(f"{stem}: {path}")
