import { useEffect, useMemo, useState } from "react";
import { Link, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }
  return response.json();
}

function combineTags(dataset) {
  return [
    dataset.omics_type,
    dataset.species,
    ...(dataset.disease_values || []),
    ...(dataset.tissue_values || []),
    ...(dataset.condition_values || []),
  ].filter(Boolean);
}

function TagList({ tags, accent = "soft" }) {
  return (
    <div className="tag-list">
      {tags.map((tag) => (
        <span className={`tag ${accent}`} key={tag}>
          {tag}
        </span>
      ))}
    </div>
  );
}

function Layout({ children }) {
  const location = useLocation();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-panel">
          <p className="eyebrow">Research Demo</p>
          <h1>Multi-Omics Warehouse</h1>
          <p>Immutable `.h5ad` storage, SQL metadata indexing, and lazy cell-level retrieval in one local prototype.</p>
        </div>
        <nav>
          <Link className={location.pathname === "/" ? "active" : ""} to="/">
            Dataset Browser
          </Link>
          <Link className={location.pathname.startsWith("/cells") ? "active" : ""} to="/cells">
            Row Query
          </Link>
        </nav>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}

function DatasetBrowser() {
  const [options, setOptions] = useState({ diseases: [], tissues: [], omics_types: [] });
  const [filters, setFilters] = useState({ disease: "", tissue: "", omics_type: "" });
  const [datasets, setDatasets] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/metadata/options")
      .then(setOptions)
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    api(`/datasets?${params.toString()}`)
      .then(setDatasets)
      .catch((err) => setError(err.message));
  }, [filters]);

  const summary = useMemo(() => {
    const cellCount = datasets.reduce((total, dataset) => total + dataset.n_cells, 0);
    return {
      datasets: datasets.length,
      cells: cellCount,
      omics: new Set(datasets.map((dataset) => dataset.omics_type)).size,
    };
  }, [datasets]);

  return (
    <section>
      <header className="hero card hero-card">
        <div>
          <p className="eyebrow">Dataset Browser</p>
          <h2>Browse across multiple omics layers with metadata-first discovery</h2>
          <p>
            Use metadata filters to narrow the catalog, then open a dataset for a dedicated summary view with tags,
            cohort context, and sample preview.
          </p>
        </div>
        <div className="hero-stats">
          <div>
            <strong>{summary.datasets}</strong>
            <span>datasets</span>
          </div>
          <div>
            <strong>{summary.cells}</strong>
            <span>indexed rows</span>
          </div>
          <div>
            <strong>{summary.omics}</strong>
            <span>omics types</span>
          </div>
        </div>
      </header>

      <div className="card filters">
        <label>
          Disease
          <select value={filters.disease} onChange={(e) => setFilters({ ...filters, disease: e.target.value })}>
            <option value="">All</option>
            {options.diseases.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label>
          Tissue
          <select value={filters.tissue} onChange={(e) => setFilters({ ...filters, tissue: e.target.value })}>
            <option value="">All</option>
            {options.tissues.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label>
          Omics Type
          <select value={filters.omics_type} onChange={(e) => setFilters({ ...filters, omics_type: e.target.value })}>
            <option value="">All</option>
            {options.omics_types.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <div className="filter-note">
          <strong>{datasets.length}</strong>
          <span>matching datasets</span>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="dataset-grid">
        {datasets.map((dataset) => (
          <article className="card dataset-card" key={dataset.dataset_id}>
            <div className="dataset-card-top">
              <span className="dataset-id">{dataset.dataset_id}</span>
              <span className="metric-pill">{dataset.n_cells} rows</span>
            </div>
            <h3>
              <Link to={`/datasets/${dataset.dataset_id}`}>{dataset.title}</Link>
            </h3>
            <p className="dataset-description">{dataset.description}</p>
            <TagList tags={combineTags(dataset)} />
            <div className="dataset-stats">
              <div>
                <span>Omics</span>
                <strong>{dataset.omics_type}</strong>
              </div>
              <div>
                <span>Species</span>
                <strong>{dataset.species}</strong>
              </div>
            </div>
            <div className="dataset-actions">
              <Link className="inline-link" to={`/datasets/${dataset.dataset_id}`}>
                Open dataset
              </Link>
              <Link className="inline-link" to={`/cells?dataset_id=${dataset.dataset_id}`}>
                Query rows
              </Link>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function DatasetDetail() {
  const { datasetId } = useParams();
  const navigate = useNavigate();
  const [dataset, setDataset] = useState(null);
  const [embedding, setEmbedding] = useState(null);
  const [error, setError] = useState("");
  const [embeddingError, setEmbeddingError] = useState("");

  useEffect(() => {
    api(`/datasets/${datasetId}`)
      .then(setDataset)
      .catch((err) => setError(err.message));
    api(`/datasets/${datasetId}/embedding`)
      .then((data) => {
        setEmbedding(data);
        setEmbeddingError("");
      })
      .catch((err) => setEmbeddingError(err.message));
  }, [datasetId]);

  if (error) return <p className="error">{error}</p>;
  if (!dataset) return <p>Loading dataset...</p>;

  const tags = combineTags(dataset);

  return (
    <section>
      <header className="hero card detail-hero">
        <div>
          <p className="eyebrow">Dataset Detail</p>
          <h2>{dataset.title}</h2>
          <p>{dataset.description}</p>
          <TagList tags={tags} accent="bright" />
        </div>
        <div className="hero-actions">
          <button onClick={() => navigate(`/cells?dataset_id=${dataset.dataset_id}`)}>Explore Rows</button>
        </div>
      </header>

      <div className="detail-grid">
        <div className="card narrative-card">
          <h3>Dataset Snapshot</h3>
          <p>
            This dataset represents a <strong>{dataset.omics_type}</strong> study in <strong>{dataset.species}</strong>
            , indexed as <strong>{dataset.dataset_id}</strong>. It currently exposes <strong>{dataset.n_cells}</strong>
            indexed rows and <strong>{dataset.sample_count}</strong> unique samples for metadata-first exploration.
          </p>
          <p>
            The metadata layer stays in PostgreSQL while the source matrix remains in the original `.h5ad` file. This
            keeps the demo aligned with the design goal of immutable ingestion plus lazy subset loading.
          </p>
          <div className="info-block">
            <span>Source file</span>
            <code>{dataset.file_path}</code>
          </div>
        </div>

        <div className="card">
          <h3>Metadata</h3>
          <dl className="meta-list">
            <div>
              <dt>Dataset ID</dt>
              <dd>{dataset.dataset_id}</dd>
            </div>
            <div>
              <dt>Omics Type</dt>
              <dd>{dataset.omics_type}</dd>
            </div>
            <div>
              <dt>Species</dt>
              <dd>{dataset.species}</dd>
            </div>
            <div>
              <dt>Indexed Rows</dt>
              <dd>{dataset.n_cells}</dd>
            </div>
            <div>
              <dt>Samples</dt>
              <dd>{dataset.sample_count}</dd>
            </div>
            <div>
              <dt>Disease</dt>
              <dd>{dataset.disease_values.join(", ") || "-"}</dd>
            </div>
            <div>
              <dt>Tissue</dt>
              <dd>{dataset.tissue_values.join(", ") || "-"}</dd>
            </div>
            <div>
              <dt>Condition</dt>
              <dd>{dataset.condition_values.join(", ") || "-"}</dd>
            </div>
          </dl>
        </div>
      </div>

      <EmbeddingPanel embedding={embedding} error={embeddingError} dataset={dataset} />

      <div className="detail-grid lower-grid">
        <div className="card">
          <h3>Sample Preview</h3>
          <table>
            <thead>
              <tr>
                <th>Sample</th>
                <th>Disease</th>
                <th>Tissue</th>
                <th>Condition</th>
              </tr>
            </thead>
            <tbody>
              {dataset.sample_preview.map((sample) => (
                <tr key={sample.sample_id}>
                  <td>{sample.sample_id}</td>
                  <td>{sample.disease || "-"}</td>
                  <td>{sample.tissue || "-"}</td>
                  <td>{sample.condition || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h3>Why This Dataset Matters</h3>
          <div className="stack-list">
            <div className="stack-item">
              <span className="stack-kicker">Discovery</span>
              <p>Use metadata filters to position this dataset within the larger warehouse without loading matrices.</p>
            </div>
            <div className="stack-item">
              <span className="stack-kicker">Cross-dataset query</span>
              <p>Move into row query to ask for populations like T cells or bulk profiles across indexed studies.</p>
            </div>
            <div className="stack-item">
              <span className="stack-kicker">Lazy access</span>
              <p>Expression values are fetched only for selected indices, directly from the immutable source file.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function CellQuery() {
  const location = useLocation();
  const search = new URLSearchParams(location.search);
  const [filters, setFilters] = useState({
    cell_type: search.get("cell_type") || "",
    disease: search.get("disease") || "",
    dataset_id: search.get("dataset_id") || "",
  });
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState([]);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");

  async function runQuery(nextFilters = filters) {
    const params = new URLSearchParams();
    Object.entries(nextFilters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    try {
      const data = await api(`/cells?${params.toString()}`);
      setResults(data);
      setSelected([]);
      setPreview(null);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    runQuery(filters);
  }, []);

  function toggleSelection(item) {
    setSelected((current) => {
      const exists = current.some(
        (entry) => entry.dataset_id === item.dataset_id && entry.obs_index === item.obs_index
      );
      if (exists) {
        return current.filter(
          (entry) => !(entry.dataset_id === item.dataset_id && entry.obs_index === item.obs_index)
        );
      }
      if (current.length > 0 && current[0].dataset_id !== item.dataset_id) {
        return [item];
      }
      return [...current, item];
    });
  }

  async function loadPreview() {
    if (selected.length === 0) return;
    const datasetId = selected[0].dataset_id;
    try {
      const data = await api("/cells/data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset_id: datasetId,
          indices: selected.map((item) => item.obs_index),
        }),
      });
      setPreview(data);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section>
      <header className="page-head">
        <div>
          <h2>Row Query</h2>
          <p>Search indexed rows across datasets using metadata. Expression values are loaded only on preview.</p>
        </div>
      </header>

      <div className="card filters">
        <label>
          Row Type
          <input
            value={filters.cell_type}
            placeholder="T cell or Bulk profile"
            onChange={(e) => setFilters({ ...filters, cell_type: e.target.value })}
          />
        </label>
        <label>
          Disease
          <input
            value={filters.disease}
            placeholder="lung cancer"
            onChange={(e) => setFilters({ ...filters, disease: e.target.value })}
          />
        </label>
        <label>
          Dataset ID
          <input
            value={filters.dataset_id}
            placeholder="optional"
            onChange={(e) => setFilters({ ...filters, dataset_id: e.target.value })}
          />
        </label>
        <button onClick={() => runQuery()}>Run Query</button>
      </div>

      {selected.length > 0 ? (
        <div className="selection-bar">
          <span>
            {selected.length} row(s) selected from <strong>{selected[0].dataset_id}</strong>
          </span>
          <button onClick={loadPreview}>Preview Data</button>
        </div>
      ) : null}

      {error ? <p className="error">{error}</p> : null}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Select</th>
              <th>Dataset</th>
              <th>Obs Index</th>
              <th>Sample</th>
              <th>Row Type</th>
              <th>Cluster</th>
            </tr>
          </thead>
          <tbody>
            {results.map((row) => {
              const checked = selected.some(
                (item) => item.dataset_id === row.dataset_id && item.obs_index === row.obs_index
              );
              return (
                <tr key={`${row.dataset_id}:${row.obs_index}`}>
                  <td>
                    <input type="checkbox" checked={checked} onChange={() => toggleSelection(row)} />
                  </td>
                  <td>{row.dataset_id}</td>
                  <td>{row.obs_index}</td>
                  <td>{row.sample_id || "-"}</td>
                  <td>{row.cell_type || "-"}</td>
                  <td>{row.cluster || "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {preview ? <DataPreview preview={preview} /> : null}
    </section>
  );
}

function DataPreview({ preview }) {
  const genes = preview.genes.slice(0, 6);
  const rows = preview.expression.map((values, index) => ({
    cell: preview.indices[index],
    obs: preview.obs[index],
    values: values.slice(0, 6),
  }));

  return (
    <section className="card">
      <h3>Data Preview</h3>
      <p>Showing the first six features for the selected rows from the source `.h5ad` file.</p>
      <table>
        <thead>
          <tr>
            <th>Obs Index</th>
            <th>Sample</th>
            <th>Row Type</th>
            {genes.map((gene) => (
              <th key={gene}>{gene}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.cell}>
              <td>{row.cell}</td>
              <td>{row.obs.sample_id || "-"}</td>
              <td>{row.obs.cell_type || "-"}</td>
              {row.values.map((value, index) => (
                <td key={`${row.cell}:${genes[index]}`}>{value.toFixed(1)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function EmbeddingPanel({ embedding, error, dataset }) {
  if (error) {
    return (
      <section className="card embedding-card">
        <h3>Embedding</h3>
        <p className="error">{error}</p>
      </section>
    );
  }

  if (!embedding) {
    return (
      <section className="card embedding-card">
        <h3>Embedding</h3>
        <p>Loading embedding...</p>
      </section>
    );
  }

  const basisLabel = embedding.basis === "pca" ? "PCA" : "UMAP";
  const expected = dataset.omics_type.toLowerCase().startsWith("bulk") ? "PCA" : "UMAP";

  return (
    <section className="card embedding-card">
      <div className="embedding-head">
        <div>
          <h3>{basisLabel} Overview</h3>
          <p>
            {embedding.returned_points > 0
              ? `${embedding.returned_points} of ${embedding.total_points} rows shown${embedding.is_sampled ? " (sampled)" : ""}.`
              : `No ${expected} coordinates are available for this dataset.`}
          </p>
        </div>
        <span className="metric-pill">{basisLabel}</span>
      </div>
      {embedding.points.length > 0 ? (
        <ScatterPlot points={embedding.points} basis={basisLabel} />
      ) : (
        <div className="empty-state">
          Available embeddings: {embedding.available_bases.length ? embedding.available_bases.join(", ") : "none"}
        </div>
      )}
    </section>
  );
}

function ScatterPlot({ points, basis }) {
  const width = 760;
  const height = 420;
  const padding = 32;
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  const labels = [...new Set(points.map((point) => point.label || "Unknown"))].slice(0, 12);
  const palette = ["#145a46", "#b35c1e", "#315f9c", "#8a4b91", "#2b7a78", "#b23a48", "#6a7d23", "#6b5b95"];
  const colorFor = (label) => palette[Math.max(labels.indexOf(label), 0) % palette.length];
  const scaleX = (value) => padding + ((value - minX) / xSpan) * (width - padding * 2);
  const scaleY = (value) => height - padding - ((value - minY) / ySpan) * (height - padding * 2);

  return (
    <div className="embedding-plot-wrap">
      <svg className="embedding-plot" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${basis} scatter plot`}>
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} />
        {points.map((point) => {
          const label = point.label || "Unknown";
          return (
            <circle
              key={`${point.obs_index}:${point.x}:${point.y}`}
              cx={scaleX(point.x)}
              cy={scaleY(point.y)}
              r="4"
              fill={colorFor(label)}
            >
              <title>{`${label} | ${point.sample_id || "no sample"} | row ${point.obs_index}`}</title>
            </circle>
          );
        })}
        <text x={width - padding} y={height - 8} textAnchor="end">
          {basis} 1
        </text>
        <text x={10} y={padding} transform={`rotate(-90 10 ${padding})`}>
          {basis} 2
        </text>
      </svg>
      <div className="embedding-legend">
        {labels.map((label) => (
          <span key={label}>
            <i style={{ backgroundColor: colorFor(label) }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DatasetBrowser />} />
        <Route path="/datasets/:datasetId" element={<DatasetDetail />} />
        <Route path="/cells" element={<CellQuery />} />
      </Routes>
    </Layout>
  );
}
