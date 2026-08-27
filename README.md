# POLER-Quantum-RS

**`.poler` / `.pqw` — POLER Quantum Weights + POLER Quantum Core.** Бинарный формат
фазовых весов POLER[Ψ] и вычислительное ядро на Rust — экосистема
[POLER-Quantum](https://github.com/Kotokvit/POLER-Quantum).
Два кирпича **RQ1** из `rust-core-roadmap.md`: контейнер состояния
(`pqw`) и statevector-движок с Born-сэмплированием (`pqc`).

Оба крейта собираются **без единой внешней зависимости** — ни serde, ни
memmap2, ни faer, ни rand: SHA-256 (FIPS 180-4), FNV-1a64, mmap,
xoshiro256++ и SIMD-ядра реализованы внутри, финальный бинарник
автономен и воспроизводим.

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

## Вычислительное ядро `pqc` (v0.1.1, RQ1)

Statevector-движок с анзацем `R_y(arccos p)` и Born-сэмплированием поверх
контейнера — полностью независимый исполняемый бинарник без Python и Qiskit.
Ключевое тождество: **собственное значение McWeeny `λ = (1+p)/2` — это
P(b = 0)**, а `P(b = 1) = (1−p)/2`; очистка McWeeny заостряет
Born-распределение к детерминированным битам.

| Движок | Условие | Память | Выстрел |
|---|---|---|---|
| `Statevector` | `d_pol ≤ 20` (настраивается) | `2^d_pol × 16 B` | `O(d_pol)` |
| `PhaseAnsatz` | любое `d_pol` | `O(nnz)` | `O(nnz + d_pol/64)` |

LENS-пропуски декодируются как честные монеты (фон), хранимые дуги —
спайки; фоновый вес сэмплируется popcount-трюком (`Binomial(64, ½)` за
одно случайное слово). Ядра авто-векторизуются (блочный обход пар
`(i, i + 2^q)`), параллельность — детерминированный fork-join на
`std::thread` без rayon.

```rust
use pqc::{Ansatz, LoadOptions, Rng};
use pqw::{PqwReader, PqwWriter};

let bytes = PqwWriter::new(12)?.add_phase(1, -1.0)?.to_bytes()?;
let reader = PqwReader::from_bytes(&bytes)?;
let ansatz = Ansatz::from_reader(&reader, &LoadOptions::default())?;
let mut rng = Rng::seed_from_u64(42);
let report = ansatz.sample(&mut rng, 1024, 8)?;   // Born: топ-K + маргиналы
```

Замеры (2 vCPU, release): анзац 2²⁰ амплитуд — 16 мс; 100k выстрелов —
13 мс; product-движок d=65536, 10k выстрелов — 45 мс. Полная спецификация —
[`docs/quantum-core.md`](docs/quantum-core.md).

```console
$ pqw gen state.poler 4096 512 --eps 0.05   # контейнер
$ pqc run state.poler --shots 4096          # Born-сэмплирование
engine    : product (d_pol=4096, nnz=477)
shots     : 4096  seed: 42  distinct: 189
hamming weight: mean 2044.19 (theory 2044.69)  var 962.54 (theory 982.37)

$ pqc demo --n 12                            # полный конвейер в памяти
engine    : statevector (12 qubits, 4096 amplitudes)
top-8 исходов:  |001110001110⟩  count 94  p̂=0.0229  P=0.0207
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

$ pqc run state.poler --shots 8192 --purify 2 --verify --marginals
$ pqc demo --n 16 --seed 7                   # конвейер без файла
```

## Тесты

`cargo test` — **152 теста + 5 doc-тестов** (68 на `pqw` + 89 на `pqc`):

- известные векторы SHA-256 (NIST) и FNV-1a64;
- **golden-layout**: побайтовая проверка всех смещений (`0x00..0x80` + payload);
- **матрица повреждений** (15 кейсов): битфлипы заголовка/топологии/фаз,
  усечение, мусор в конце, зарезервированные биты, несогласованные длины;
- roundtrip в границах квантилизации (случайные состояния, d = 512…65537);
- zero-copy: заимствование фаз и индексов без копирования;
- McWeeny: подпись заголовка == пересчёт, сходимость, сохранение тритов;
- mmap-сценарий: запись → отображение → разбор → верификация;
- **паритет с аналитикой** (26): тензорная структура R_y, состояние Белла,
  анзац из фаз против формулы произведения амплитуд — допуск 1e-12;
- **статистика Born** (14): равномерность и согласие с теорией в 5σ,
  product-движок против statevector-моментов, фон = Binomial(d, ½);
- **мост pqw → pqc** (12): LENS-фон, McWeeny-заострение, порча payload,
  mmap end-to-end, побитовая воспроизводимость;
- ГПСЧ: потоки, jump, равномерность, покрытие всех 64 бит.

## Roadmap

- **v0.1 (pqw)** — формат v1 + CLI + mmap + McWeeny-модуль
- **v0.1.1 (pqc, здесь)** — ✅ ядро RQ1: statevector, анзац `Ry(arccos p)`,
  Born sampling, два движка, SIMD-ядра без зависимостей
- **RQ4** — паритет с qiskit < 1e-12 на кросс-наборе схем
- **RQ2** — ✅ выполнена в [POLER-Quantum v1.1.0](https://github.com/Kotokvit/POLER-Quantum) (Python)
- **v0.2 (идеи)** — режим без кривизны (4 дуги/байт), блочный RLE топологии,
  хранение антисимметричных весов `J = A − Aᵀ` (верхний треугольник)

## License

MIT — см. [LICENSE](LICENSE).
