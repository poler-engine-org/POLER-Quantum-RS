import subprocess, time, os, sys
from pathlib import Path

sources = [
    Path('/home/vitalij/Документи'),
    Path('/home/vitalij/Сфера_Предела_Архив'),
    Path('/home/vitalij/Стільниця/Eteryya'),
    Path('/home/vitalij/Стільниця/POLER-ERI-ALL-UNIFIED'),
]

checkpoint_path = Path('/home/vitalij/Стільниця/POLER-Quantum-RS_repo/master_learned_state.pqw')
log_path = Path('/home/vitalij/Стільниця/POLER-Quantum-RS_repo/deep_training_telemetry.log')

print('🚀 Инициализация фонового глубокого обучения POLER Active Inference...')
print('📁 Чекпоинт:', checkpoint_path)
print('📊 Лог телеметрии:', log_path)

all_files = []
for s in sources:
    if s.exists():
        for p in s.rglob('*'):
            if p.is_file() and p.suffix.lower() in ['.txt', '.md', '.rs', '.py', '.json', '.c', '.h', '.cpp']:
                try:
                    if 200 < p.stat().st_size < 5_000_000:
                        all_files.append(p)
                except:
                    pass

print(f'🎯 Отобрано {len(all_files)} файлов для сквозного обучения.')
start_time = time.time()

with open(log_path, 'w', encoding='utf-8') as log_f:
    log_f.write('=== ПОЛНОМАСШТАБНОЕ ОБУЧЕНИЕ POLER ACTIVE INFERENCE ===\n\n')

    for idx, fpath in enumerate(all_files, 1):
        try:
            cmd = [
                '/home/vitalij/Стільниця/POLER-Quantum-RS_repo/target/release/pqc',
                'stream',
                '--file', str(fpath),
                '--dim', '4096',
                '--steps', '10',
                '--shots', '20000',
                '--out', str(checkpoint_path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if res.returncode == 0:
                lines = res.stdout.splitlines()
                tok_line = [l for l in lines if 'токенов' in l]
                loss_line = [l for l in lines if 'loss' in l]
                status_str = f'[{idx}/{len(all_files)}] {fpath.name[:35]:<35} | {tok_line[0] if tok_line else ""} | {loss_line[0] if loss_line else ""}'
                log_f.write(status_str + '\n')
                log_f.flush()
                if idx % 50 == 0:
                    elapsed = time.time() - start_time
                    print(f'⚡ Пройдено {idx}/{len(all_files)} файлов ({elapsed/60:.1f} мин). Чекпоинт обновлен.')
        except Exception:
            continue

print(f'\n✅ Фоновое обучение завершено! Итоговое время: {(time.time() - start_time)/60:.2f} минут.')
