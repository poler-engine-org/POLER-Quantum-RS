import urllib.request, urllib.parse, json, re, time, subprocess, os
from pathlib import Path

print('🌐 Запуск боевого интернет-краулера и потокового обучения POLER...')

checkpoint_path = Path('/home/vitalij/Стільниця/POLER-Quantum-RS_repo/internet_master_state.pqw')
log_path = Path('/home/vitalij/Стільниця/POLER-Quantum-RS_repo/internet_training_telemetry.log')

seed_sources = [
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0001-gate-test-everything.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0130-traits-move-and-copy.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0141-travis-drop-32bit-linux.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0160-self-in-type-definitions.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0195-associated-items.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0235-collections-conventions.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0243-trait-based-exception-handling.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0246-well-formed-types.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0255-object-safety.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0385-module-system-cleanup.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0401-coherence-orphan-rules.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0447-no-implicit-prelude.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0458-send-sync-impls.md',
    'https://raw.githubusercontent.com/rust-lang/rfcs/master/text/0505-associated-items-2.md',
    'https://raw.githubusercontent.com/qiskit-community/qiskit-algorithms/main/qiskit_algorithms/minimum_eigensolvers/vqe.py',
    'https://raw.githubusercontent.com/qiskit-community/qiskit-algorithms/main/qiskit_algorithms/amplitude_amplifiers/grover.py',
    'https://raw.githubusercontent.com/qiskit-community/qiskit-algorithms/main/qiskit_algorithms/eigensolvers/numpy_eigensolver.py',
    'https://raw.githubusercontent.com/scipy/scipy/main/scipy/sparse/linalg/_eigen/arpack/arpack.py',
    'https://raw.githubusercontent.com/scipy/scipy/main/scipy/linalg/_decomp_schur.py',
    'https://raw.githubusercontent.com/scipy/scipy/main/scipy/linalg/_decomp_svd.py',
    'https://raw.githubusercontent.com/scipy/scipy/main/scipy/linalg/_decomp_cholesky.py',
    'https://raw.githubusercontent.com/torvalds/linux/master/include/linux/math64.h',
    'https://raw.githubusercontent.com/torvalds/linux/master/include/linux/rational.h',
    'https://raw.githubusercontent.com/torvalds/linux/master/include/linux/atomic.h',
    'https://raw.githubusercontent.com/torvalds/linux/master/include/linux/rbtree.h',
    'https://raw.githubusercontent.com/torvalds/linux/master/include/linux/list.h',
    'https://raw.githubusercontent.com/torvalds/linux/master/kernel/sched/core.c',
    'https://raw.githubusercontent.com/torvalds/linux/master/kernel/sched/fair.c',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Quantum_mechanics&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=General_relativity&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Free_energy_principle&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Grassmannian&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Wheeler%E2%80%93DeWitt_equation&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Differential_geometry&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Quantum_electrodynamics&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Lie_group&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Topological_quantum_field_theory&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Idempotence&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Information_theory&format=json',
    'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=Lyapunov_stability&format=json',
]

start_time = time.time()
target_duration = 20 * 60
chunk_size = 1024

temp_chunk = Path('/home/vitalij/.gemini/antigravity-cli/brain/5e1b6299-4eaa-4a27-82cc-3d6583593e27/scratch/current_stream_chunk.txt')
temp_chunk.parent.mkdir(parents=True, exist_ok=True)

with open(log_path, 'w', encoding='utf-8') as log_f:
    log_f.write('=== НЕПРЕРЫВНОЕ ПОТОКОВОЕ ОБУЧЕНИЕ ИЗ ИНТЕРНЕТА (20 МИНУТ) ===\n\n')
    log_f.flush()

    total_chunks = 0
    total_bytes_streamed = 0

    while (time.time() - start_time) < target_duration:
        for url in seed_sources:
            if (time.time() - start_time) >= target_duration:
                break
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'POLER-Active-Inference/3.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    raw_data = response.read().decode('utf-8', errors='ignore')
                    
                    for i in range(0, len(raw_data), chunk_size):
                        if (time.time() - start_time) >= target_duration:
                            break
                        chunk = raw_data[i:i + chunk_size].strip()
                        if len(chunk) < 50:
                            continue
                        
                        temp_chunk.write_text(chunk, encoding='utf-8')
                        total_bytes_streamed += len(chunk)
                        total_chunks += 1

                        cmd = [
                            '/home/vitalij/.cargo/bin/pqc',
                            'stream',
                            '--file', str(temp_chunk),
                            '--dim', '4096',
                            '--steps', '10',
                            '--shots', '20000',
                            '--out', str(checkpoint_path)
                        ]
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                        if res.returncode == 0:
                            elapsed = time.time() - start_time
                            remain = max(0, target_duration - elapsed)
                            lines = res.stdout.splitlines()
                            loss_line = [l for l in lines if 'loss' in l]
                            qcm_line = [l for l in lines if 'qcm' in l]
                            status = f'[{time.strftime("%H:%M:%S")} | Chunk #{total_chunks:<5} | Streamed: {total_bytes_streamed/1024:.1f} KB | {loss_line[0] if loss_line else ""} | {qcm_line[0] if qcm_line else ""} | Осталось: {remain/60:.1f} мин'
                            log_f.write(status + '\n')
                            log_f.flush()
            except Exception:
                continue

    total_time = (time.time() - start_time) / 60
    log_f.write(f'\n✅ 20-минутный сеанс завершен! Всего перемолото: {total_chunks} чанков ({total_bytes_streamed/1024/1024:.2f} MB), время: {total_time:.2f} мин.\n')
