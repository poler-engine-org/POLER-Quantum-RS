# POLER-Quantum-RS

**`.poler` / `.pqw` — POLER Quantum Weights.** Бинарный формат фазовых весов
POLER[Ψ] и Rust-ядро экосистемы [POLER-Quantum](https://github.com/Kotokvit/POLER-Quantum).
Первый кирпич **RQ1** из `rust-core-roadmap.md`: бинарный формат состояния —
контракт, общий для инференса и обучения.

Крейт `pqw` собирается **без единой внешней зависимости** — ни serde, ни
memmap2, ни libc: SHA-256 (FIPS 180-4), FNV-1a64 и mmap реализованы внутри,
финальный бинарник автономен и воспроизводим.

## Почему не GGUF / SafeTensors / .pt

| Критерий | Обычные форматы | `.poler` / `.pqw` |
|---|---|---|
| Хранение весов | INT4/INT8-сетки + scale-множители на блок | фазовые триты `{−1, 0, +1}` + 6-битная кривизна σ |
| Загрузка в память | пошаговое чтение и распаковка в RAM | zero-copy mmap: файл = память, «instant cold start» |
| Сжатие | фиксированная битность на всю матрицу | sparse LENS: дуги с \|p\| < ε не хранятся вовсе |
| Аппаратная адаптация | требует FP32/FP16 FMA-умножителей | multiplier-less: трит = знак, σ/63 — shift-and-add |
| Контроль шума | ошибки квантования накапливаются | McWeeny-инвариант `P² = P` вшит в заголовок |

## Формат v1 — байтовая карта

```text
0x00   8    magic "POLER_QW"
0x08   4    format_version (u32 LE, = 1)
0x0C   4    d_pol (u32 LE)
0x10   16   гиперпараметры: eta, gamma, rho, epsilon_threshold (f32 LE × 4)
0x20   8    McWeeny: max |λ² − λ| по хранимым дугам (f64 LE)
0x28   24   payload digest: SHA-256(topology ‖ phases), усечённый до 24 байт
0x40   64   таблица смещений: topology/phase offset+len, nnz, flags,
             reserved (= 0), header checksum (FNV-1a64 по 0x00..0x78)
0x80   ...  sparse LENS-топология: nnz × u16 (d_pol ≤ 65536) или nnz × u32 LE
       ...  фазовые блоки: 1 байт на дугу —
             биты 0..1: трит {−1, 0, +1}; биты 2..7: кривизна σ ∈ [0, 63]
EOF
```

Декодирование дуги: `p̂ = trit · (σ / 63)`, фазовый угол `θ̂ = arccos(p̂)` —
готовый угол для анзаца `Ry(arccos p)`. Граница ошибки квантования
`|p̂ − p| ≤ 1/126`. Полная спецификация — [`docs/pqw-format.md`](docs/pqw-format.md).

## Быстрый старт

```rust
use pqw::{PqwReader, PqwWriter, Mmap};
use std::path::Path;

// Запись: явные дуги или плотное состояние с LENS-фильтром |p| ≥ ε
let mut w = PqwWriter::new(4096)?;
w.hyperparams(0.01, 0.1, 0.99, 0.05);
w.add_phase(7, 0.5)?;              // явная дуга — LENS не фильтрует
// w.add_state(&dense_state)?;     // плотный режим: |p| < ε не попадёт в файл
w.write_to("state.poler")?;

// Чтение: zero-copy mmap (unix), без распаковки
let map = Mmap::open(Path::new("state.poler"))?;
let r = PqwReader::from_bytes(map.as_slice())?;
for (index, p) in r.decoded() {
    // (index, p̂) — срезы заимствованы напрямую из отображения файла
}
r.verify_payload()?;               // digest payload — опционально и лениво
```

## McWeeny-инвариант

Трит — предельная точка потока очистки `P_new = 3P² − 2P³` (McWeeny, 1960):
кубит с треком `p` имеет собственное значение `λ = (1+p)/2`, и один шаг потока
`λ' = 3λ² − 2λ³` стягивает сильные треки к чистым фазам ±1 за 1–2 такта.
Записанный в заголовок `max |λ² − λ|` измеряет отклонение от идемпотентности
`P² = P` на момент записи; API восстанавливает инвариант на лету:

```rust
let purified = reader.purified();          // 2 шага: 0.9 → 0.9997
let deep = reader.purify_steps(5);         // глубокая очистка при необходимости
let residual = reader.mcweeny_residual();  // подпись из заголовка
```

## CLI

```console
$ pqw gen state.poler 4096 512 --eps 0.05
generated state.poler
  d_pol = 4096, arcs requested = 512, stored after LENS (eps = 0.05) = 477
  file size = 1559 bytes = 128 header + 954 topology + 477 phase bytes

$ pqw info state.poler        # дамп заголовка: гиперпараметры, nnz, McWeeny, digest
$ pqw verify state.poler      # header checksum + payload digest → OK / FAIL
$ pqw dump state.poler --limit 5
     index  tri  sigma           p         theta
         0  -1     25   -0.396825      1.978852
         6  +1     63    1.000000      0.000000
        ...
```

## Тесты

`cargo test` — **66 тестов + 2 doc-теста**:

- известные векторы SHA-256 (NIST) и FNV-1a64;
- **golden-layout**: побайтовая проверка всех смещений (`0x00..0x80` + payload);
- **матрица повреждений** (15 кейсов): битфлипы заголовка/топологии/фаз,
  усечение, мусор в конце, зарезервированные биты, несогласованные длины;
- roundtrip в границах квантилизации (случайные состояния, d = 512…65537);
- zero-copy: заимствование фаз и индексов без копирования;
- McWeeny: подпись заголовка == пересчёт, сходимость, сохранение тритов;
- mmap-сценарий: запись → отображение → разбор → верификация.

## Roadmap

- **v0.1 (здесь)** — формат v1 + CLI + mmap + McWeeny-модуль
- **RQ1** — faer/SIMD-ядро: statevector, анзац `Ry(arccos p)`, Born sampling;
  паритет с qiskit-прототипом < 1e-12; стриминг состояний из poler-engine
- **RQ2** — ✅ выполнена в [POLER-Quantum v1.1.0](https://github.com/Kotokvit/POLER-Quantum) (Python)
- **v0.2 (идеи)** — режим без кривизны (4 дуги/байт), блочный RLE топологии,
  хранение антисимметричных весов `J = A − Aᵀ` (верхний треугольник)

## License

MIT — см. [LICENSE](LICENSE).
