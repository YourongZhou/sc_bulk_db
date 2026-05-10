import { useEffect, useMemo, useState } from "react";
import { Link, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const DATA_TYPE_OPTIONS = [
  { value: "", label: "全部" },
  { value: "rna_seq", label: "RNA-seq" },
  { value: "bulk", label: "bulk" },
  { value: "fastq", label: "FASTQ" },
];
const MODALITY_ORDER = ["single_cell_h5ad", "bulk", "fastq"];
const MODALITY_LABELS = {
  single_cell_h5ad: "RNA-seq",
  bulk: "bulk",
  fastq: "FASTQ",
};
const GROUP_ORDER = [
  "plateau_high_cold",
  "tropical_heat_tolerant",
  "plain_ams_patient",
  "plain_low_altitude",
];
const GROUP_NAME_FALLBACKS = {
  plateau_high_cold: "高原高寒环境人群",
  tropical_heat_tolerant: "热带环境耐热人群",
  plain_ams_patient: "平原环境人群高原反应患者",
  plain_low_altitude: "平原环境低海拔人群",
};
const EXACT_TEXT_TRANSLATIONS = new Map([
  ["Lung Tumor Immune Atlas", "肺肿瘤免疫图谱"],
  ["Lung Immunotherapy Response Panel", "肺部免疫治疗响应面板"],
  ["Colon Inflammation Cell Map", "结肠炎症细胞图谱"],
  ["Breast Bulk Expression Panel", "乳腺 bulk 表达面板"],
  ["Liver Fibrosis Bulk Series", "肝纤维化 bulk 序列"],
  ["Colon Regulatory Accessibility Map", "结肠调控可及性图谱"],
  ["Bone Marrow ATAC Reference", "骨髓 ATAC 参考图谱"],
  ["Brain Cortex Spatial Grid", "脑皮层空间网格"],
  ["Melanoma Spatial Margin Survey", "黑色素瘤边缘空间图谱"],
  ["Ovarian DNA Variant Set", "卵巢 DNA 变异集合"],
  ["Glioma Copy Number Survey", "胶质瘤拷贝数概览"],
  ["Single-cell RNA-seq cohort focused on immune and tumor compartments in lung adenocarcinoma.", "聚焦肺腺癌免疫与肿瘤区室的单细胞 RNA-seq 队列。"],
  ["Synthetic scRNA-seq panel contrasting responder and non-responder lung cancer samples.", "用于对比肺癌应答者与非应答者样本的合成 scRNA-seq 面板。"],
  ["Single-cell RNA-seq view of epithelial and immune populations during active colitis.", "展示活动性结肠炎期间上皮与免疫细胞群体的单细胞 RNA-seq 视图。"],
  ["Bulk RNA-seq expression profiles summarizing treatment-naive breast tumor biopsies.", "概括初治乳腺肿瘤活检样本的 bulk RNA-seq 表达谱。"],
  ["Bulk RNA-seq profiles across staged fibrosis samples collected from liver biopsies.", "展示来自肝活检、不同纤维化阶段样本的 bulk RNA-seq 表达谱。"],
  ["ATAC-seq accessibility profiles highlighting inflammatory regulatory programs in colon tissue.", "突出结肠组织炎症调控程序的 ATAC-seq 可及性图谱。"],
  ["Reference ATAC-seq dataset covering hematopoietic compartments in healthy bone marrow.", "覆盖健康骨髓造血区室的 ATAC-seq 参考数据集。"],
  ["Spatial transcriptomics grid over healthy mouse cortex with region-specific neuron and glia signatures.", "覆盖健康小鼠皮层、带有区域特异性神经元和胶质细胞特征的空间转录组网格。"],
  ["Spatial transcriptomics slices covering tumor core and invasive margin in melanoma lesions.", "覆盖黑色素瘤病灶肿瘤核心与浸润边缘的空间转录组切片。"],
  ["DNA-focused variant abundance matrix summarizing recurrent alterations across ovarian tumor samples.", "概括卵巢肿瘤样本中复发性改变的 DNA 变异丰度矩阵。"],
  ["DNA copy-number style matrix for glioma samples across low- and high-grade lesions.", "展示低级别与高级别病灶胶质瘤样本的 DNA 拷贝数矩阵。"],
  ["mRNA expression profiling of PBMCs from Behcet’s disease", "白塞病 PBMC 的 mRNA 表达谱"],
  ["mRNA expression profiling of PBMCs from Behcet's disease", "白塞病 PBMC 的 mRNA 表达谱"],
]);
const TOKEN_TRANSLATIONS = [
  [/\bhuman\b/gi, "人"],
  [/\bmouse\b/gi, "小鼠"],
  [/\bhealthy\b/gi, "健康"],
  [/\bcontrol\b/gi, "对照"],
  [/\btumor\b/gi, "肿瘤"],
  [/\bpost-treatment\b/gi, "治疗后"],
  [/\bresponder\b/gi, "应答"],
  [/\bnon-responder\b/gi, "非应答"],
  [/\binflamed\b/gi, "炎症"],
  [/\bbaseline\b/gi, "基线"],
  [/\bprogressive\b/gi, "进展期"],
  [/\blung cancer\b/gi, "肺癌"],
  [/\bbreast cancer\b/gi, "乳腺癌"],
  [/\bovarian cancer\b/gi, "卵巢癌"],
  [/\bcolitis\b/gi, "结肠炎"],
  [/\bfibrosis\b/gi, "纤维化"],
  [/\bglioma\b/gi, "胶质瘤"],
  [/\bmelanoma\b/gi, "黑色素瘤"],
  [/\bBehcet[’']s disease\b/gi, "白塞病"],
  [/\bbone marrow\b/gi, "骨髓"],
  [/\blung\b/gi, "肺"],
  [/\bcolon\b/gi, "结肠"],
  [/\bbreast\b/gi, "乳腺"],
  [/\bliver\b/gi, "肝脏"],
  [/\bbrain\b/gi, "脑"],
  [/\bovary\b/gi, "卵巢"],
  [/\bskin\b/gi, "皮肤"],
  [/\bT cell\b/g, "T 细胞"],
  [/\bB cell\b/g, "B 细胞"],
  [/\bNK cell\b/g, "NK 细胞"],
  [/\bMacrophage\b/g, "巨噬细胞"],
  [/\bTumor cell\b/g, "肿瘤细胞"],
  [/\bDendritic cell\b/g, "树突细胞"],
  [/\bMonocyte\b/g, "单核细胞"],
  [/\bEpithelial\b/g, "上皮细胞"],
  [/\bFibroblast\b/g, "成纤维细胞"],
  [/\bStem cell\b/g, "干细胞"],
  [/\bMyeloid\b/g, "髓系细胞"],
  [/\bNeuron\b/g, "神经元"],
  [/\bAstrocyte\b/g, "星形胶质细胞"],
  [/\bMicroglia\b/g, "小胶质细胞"],
  [/\bOligodendrocyte\b/g, "少突胶质细胞"],
  [/\bEndothelial\b/g, "内皮细胞"],
  [/\bBulk profile\b/g, "bulk 表达谱"],
  [/\bDNA profile\b/g, "DNA 图谱"],
];

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(localizeText(error.detail) || "请求失败");
  }
  return response.json();
}

function formatCount(value) {
  if (!Number.isFinite(value)) return "-";
  return value.toLocaleString();
}

function formatBytes(value) {
  if (!value && value !== 0) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function titleForSample(sample) {
  return localizeText(sample.title) || sample.sample_code;
}

function humanizeCode(value) {
  return value
    ?.split("_")
    .filter(Boolean)
    .map((segment) => segment[0].toUpperCase() + segment.slice(1))
    .join(" ");
}

function localizeText(value) {
  if (!value) return value;
  const exact = EXACT_TEXT_TRANSLATIONS.get(value);
  if (exact) return exact;
  return TOKEN_TRANSLATIONS.reduce((current, [pattern, replacement]) => current.replace(pattern, replacement), value);
}

function modalityLabel(modality) {
  return MODALITY_LABELS[modality] || modality;
}

function formatModalities(modalities, separator = " · ") {
  if (!modalities?.length) return "仅元数据";
  return modalities.map(modalityLabel).join(separator);
}

function detailTags(sample) {
  return [
    sample.group?.group_name,
    localizeText(sample.species),
    localizeText(sample.tissue),
    localizeText(sample.condition),
    ...(sample.modalities || []).map(modalityLabel),
  ].filter(Boolean);
}

function catalogTags(sample) {
  return [sample.species, sample.tissue, sample.condition].map(localizeText).filter(Boolean);
}

function statusLabel(singleCellOk, bulkOk) {
  if (singleCellOk && bulkOk) return "已达标";
  if (singleCellOk) return "缺少 bulk";
  if (bulkOk) return "缺少 RNA-seq";
  return "覆盖不足";
}

function quotaProgress(count, minimum) {
  if (!minimum) return 0;
  return Math.min((count / minimum) * 100, 100);
}

function countModalities(samples) {
  return {
    total: samples.length,
    rnaSeq: samples.filter((sample) => sample.has_single_cell).length,
    bulk: samples.filter((sample) => sample.has_bulk).length,
    fastq: samples.filter((sample) => sample.has_fastq).length,
  };
}

function orderedGroupCodes(quotaStatus, samples, options) {
  const discovered = new Set(GROUP_ORDER);
  quotaStatus.forEach((group) => discovered.add(group.group_code));
  samples.forEach((sample) => {
    if (sample.group?.group_code) discovered.add(sample.group.group_code);
  });
  (options.group_codes || []).forEach((code) => discovered.add(code));
  return [...GROUP_ORDER.filter((code) => discovered.has(code)), ...[...discovered].filter((code) => !GROUP_ORDER.includes(code)).sort()];
}

function groupSamples(samples, groupCodes) {
  const grouped = new Map(groupCodes.map((code) => [code, []]));
  samples.forEach((sample) => {
    const code = sample.group?.group_code;
    if (!code) return;
    if (!grouped.has(code)) grouped.set(code, []);
    grouped.get(code).push(sample);
  });
  return grouped;
}

function ModalityBadges({ modalities, emptyLabel = "仅元数据" }) {
  if (!modalities?.length) {
    return (
      <div className="modality-strip">
        <span className="metric-pill muted">{emptyLabel}</span>
      </div>
    );
  }

  return (
    <div className="modality-strip">
      {modalities.map((modality) => (
        <span className="metric-pill" key={modality}>
          {modalityLabel(modality)}
        </span>
      ))}
    </div>
  );
}

function OverviewCard({ group }) {
  const groupStatus = statusLabel(group.singleCellOk, group.bulkOk);

  return (
    <article className="card overview-card">
      <div className="overview-card-head">
        <div>
          <p className="eyebrow">人群分组</p>
          <h3>{group.groupName}</h3>
        </div>
        <span className={`status-chip ${group.singleCellOk && group.bulkOk ? "complete" : "pending"}`}>{groupStatus}</span>
      </div>

      <div className="overview-meta">
        <div className="overview-meta-item">
          <span>样本数</span>
          <strong>{formatCount(group.sampleCount)}</strong>
        </div>
        <div className="overview-meta-item">
          <span>FASTQ</span>
          <strong>{formatCount(group.fastqCount)}</strong>
        </div>
      </div>

      <div className="quota-bars">
        <div className="quota-bar-row">
          <div className="quota-bar-copy">
            <span>RNA-seq</span>
            <strong>
              {formatCount(group.singleCellCount)}/{formatCount(group.minSingleCell)}
            </strong>
          </div>
          <div className="quota-bar-track" aria-hidden="true">
            <span className="quota-bar-fill" style={{ width: `${quotaProgress(group.singleCellCount, group.minSingleCell)}%` }} />
          </div>
        </div>

        <div className="quota-bar-row">
          <div className="quota-bar-copy">
            <span>bulk</span>
            <strong>
              {formatCount(group.bulkCount)}/{formatCount(group.minBulk)}
            </strong>
          </div>
          <div className="quota-bar-track" aria-hidden="true">
            <span className="quota-bar-fill secondary" style={{ width: `${quotaProgress(group.bulkCount, group.minBulk)}%` }} />
          </div>
        </div>
      </div>
    </article>
  );
}

function GroupSection({ group, samples }) {
  const visibleSummary = countModalities(samples);
  const groupStatus = statusLabel(group.singleCellOk, group.bulkOk);

  return (
    <section className="card group-section" key={group.groupCode}>
      <div className="group-section-head">
        <div className="group-section-intro">
          <p className="eyebrow">样本分组</p>
          <h3>{group.groupName}</h3>
          <p className="section-copy">下方可见数量会随当前目录筛选变化，配额状态徽标始终反映整个数据库的覆盖情况。</p>
        </div>
        <div className="group-metrics">
          <div className="group-metric">
            <span>可见样本</span>
            <strong>{formatCount(visibleSummary.total)}</strong>
          </div>
          <div className="group-metric">
            <span>RNA-seq</span>
            <strong>{formatCount(visibleSummary.rnaSeq)}</strong>
          </div>
          <div className="group-metric">
            <span>bulk</span>
            <strong>{formatCount(visibleSummary.bulk)}</strong>
          </div>
          <div className="group-metric">
            <span>FASTQ</span>
            <strong>{formatCount(visibleSummary.fastq)}</strong>
          </div>
          <div className="group-metric status-metric">
            <span>配额状态</span>
            <strong>{groupStatus}</strong>
          </div>
        </div>
      </div>

      {samples.length === 0 ? (
        <div className="empty-state">当前人群分组下没有符合筛选条件的样本。</div>
      ) : (
        <div className="dataset-grid">
          {samples.map((sample) => (
            <article className="card dataset-card" key={sample.sample_id}>
              <div className="dataset-card-top">
                <span className="dataset-id">{sample.sample_code}</span>
                <ModalityBadges modalities={sample.modalities} />
              </div>
              <div className="dataset-card-body">
                <h3>
                  <Link to={`/samples/${sample.sample_id}`}>{titleForSample(sample)}</Link>
                </h3>
                <p className="dataset-description">{localizeText(sample.description) || "暂无描述。"}</p>
              </div>
              <TagList tags={catalogTags(sample)} />
              <div className="dataset-stats">
                <div>
                  <span>组织</span>
                  <strong>{localizeText(sample.tissue) || "-"}</strong>
                </div>
                <div>
                  <span>已索引行</span>
                  <strong>{sample.has_single_cell ? formatCount(sample.single_cell_cell_count) : "未建立索引"}</strong>
                </div>
              </div>
              <div className="dataset-actions">
                <Link className="inline-link" to={`/samples/${sample.sample_id}`}>
                  查看样本
                </Link>
                {sample.has_single_cell ? (
                  <Link className="inline-link" to={`/single-cell?sample_id=${sample.sample_id}`}>
                    进入 RNA-seq 检索
                  </Link>
                ) : (
                  <span className="inline-link">无 RNA-seq 索引</span>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function groupLookup(options, quotaStatus, groupCodes) {
  const names = new Map();
  quotaStatus.forEach((group) => names.set(group.group_code, group.group_name));
  (options.group_codes || []).forEach((code, index) => {
    if (options.group_names?.[index] && !names.has(code)) {
      names.set(code, options.group_names[index]);
    }
  });
  groupCodes.forEach((code) => {
    if (!names.has(code)) names.set(code, GROUP_NAME_FALLBACKS[code] || humanizeCode(code));
  });
  return names;
}

function TagList({ tags, accent = "soft" }) {
  if (!tags.length) return null;
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
          <p className="eyebrow">数据库总览</p>
          <h1>多组学仓库</h1>
          <p>以样本为中心管理 FASTQ、RNA-seq 和 bulk 资产，并跟踪四类人群分组的配额覆盖情况。</p>
        </div>
        <nav>
          <Link className={location.pathname === "/" ? "active" : ""} to="/">
            数据库总览
          </Link>
          <Link className={location.pathname.startsWith("/single-cell") ? "active" : ""} to="/single-cell">
            RNA-seq 检索
          </Link>
          <a href="/combined-umaps.html">汇总 UMAP</a>
        </nav>
        <div className="sidebar-note">
          <span>原型架构</span>
          <p>样本是核心实体。文件按样本资产进行跟踪，而行级索引目前只存在于 RNA-seq 的 h5ad 数据中。</p>
        </div>
      </aside>
      <main className="content">
        <div className="content-inner">{children}</div>
      </main>
    </div>
  );
}

function SampleBrowser() {
  const [options, setOptions] = useState({
    group_codes: [],
    group_names: [],
    data_types: [],
    tissues: [],
    conditions: [],
    species: [],
  });
  const [quotaStatus, setQuotaStatus] = useState([]);
  const [filters, setFilters] = useState({ data_type: "", group_code: "", tissue: "", condition: "", species: "" });
  const [allSamples, setAllSamples] = useState([]);
  const [samples, setSamples] = useState([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api("/metadata/options"), api("/groups/quota-status"), api("/samples")])
      .then(([metadata, quota, sampleList]) => {
        setOptions(metadata);
        setQuotaStatus(quota);
        setAllSamples(sampleList);
        setError("");
      })
      .catch((err) => {
        setError(err.message);
      });
  }, []);

  useEffect(() => {
    setCatalogLoading(true);
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    api(`/samples?${params.toString()}`)
      .then((data) => {
        setSamples(data);
        setError("");
        setCatalogLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setCatalogLoading(false);
      });
  }, [filters]);

  const groupCodes = useMemo(() => orderedGroupCodes(quotaStatus, allSamples, options), [allSamples, options, quotaStatus]);
  const groupNames = useMemo(() => groupLookup(options, quotaStatus, groupCodes), [groupCodes, options, quotaStatus]);
  const overviewGroups = useMemo(() => {
    const allSamplesByGroup = groupSamples(allSamples, groupCodes);
    const quotaByCode = new Map(quotaStatus.map((group) => [group.group_code, group]));

    return groupCodes.map((groupCode) => {
      const group = quotaByCode.get(groupCode);
      const groupItems = allSamplesByGroup.get(groupCode) || [];
      return {
        groupCode,
        groupName: group?.group_name || groupNames.get(groupCode) || humanizeCode(groupCode),
        sampleCount: groupItems.length,
        singleCellCount: groupItems.filter((sample) => sample.has_single_cell).length,
        bulkCount: groupItems.filter((sample) => sample.has_bulk).length,
        fastqCount: groupItems.filter((sample) => sample.has_fastq).length,
        minSingleCell: group?.min_single_cell_samples || 0,
        minBulk: group?.min_bulk_samples || 0,
        singleCellOk: Boolean(group?.single_cell_ok),
        bulkOk: Boolean(group?.bulk_ok),
      };
    });
  }, [allSamples, groupCodes, groupNames, quotaStatus]);
  const filteredGroups = useMemo(() => groupSamples(samples, groupCodes), [groupCodes, samples]);
  const summary = useMemo(() => countModalities(allSamples), [allSamples]);
  const visibleSummary = useMemo(() => countModalities(samples), [samples]);
  const activeFilterCount = Object.values(filters).filter(Boolean).length;
  const dataTypeOptions = useMemo(
    () => DATA_TYPE_OPTIONS.filter((option) => !option.value || options.data_types.includes(option.value)),
    [options.data_types]
  );
  const quotaRows = useMemo(() => {
    const quotaByCode = new Map(quotaStatus.map((group) => [group.group_code, group]));
    return groupCodes
      .map((groupCode) => quotaByCode.get(groupCode))
      .filter(Boolean);
  }, [groupCodes, quotaStatus]);

  return (
    <section className="page-section">
      <header className="hero card hero-card browser-hero">
        <div className="hero-copy">
          <p className="eyebrow">数据库总览</p>
          <h2>查看整个库中 RNA-seq、bulk 和 FASTQ 的覆盖情况</h2>
          <p>上方概览始终保持全局统计。下方样本目录按人群分组展示，并可按数据类型、组织、条件和物种筛选。</p>
        </div>
        <div className="hero-stats overview-hero-stats">
          <div>
            <strong>{formatCount(summary.total)}</strong>
            <span>总样本数</span>
          </div>
          <div>
            <strong>{formatCount(summary.rnaSeq)}</strong>
            <span>RNA-seq 样本</span>
          </div>
          <div>
            <strong>{formatCount(summary.bulk)}</strong>
            <span>bulk 样本</span>
          </div>
          <div>
            <strong>{formatCount(summary.fastq)}</strong>
            <span>FASTQ 样本</span>
          </div>
        </div>
      </header>

      {error ? <p className="error">{error}</p> : null}

      <section className="overview-grid">
        {overviewGroups.map((group) => (
          <OverviewCard group={group} key={group.groupCode} />
        ))}
      </section>

      <div className="card filters-card">
        <div className="filters-head">
          <div>
            <p className="eyebrow">样本目录</p>
            <h3>筛选当前可见样本</h3>
          </div>
          {activeFilterCount > 0 ? (
            <button
              className="secondary-button"
              onClick={() => setFilters({ data_type: "", group_code: "", tissue: "", condition: "", species: "" })}
              type="button"
            >
              清空筛选
            </button>
          ) : null}
        </div>
        <div className="filter-pills" role="tablist" aria-label="数据类型筛选">
          {dataTypeOptions.map((option) => (
            <button
              className={`filter-pill ${filters.data_type === option.value ? "active" : ""}`}
              key={option.value || "all"}
              onClick={() => setFilters((current) => ({ ...current, data_type: option.value }))}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
        <p className="filters-helper">概览卡片和配额徽标保持全局不变，只有下方按组展示的样本目录会响应这些筛选。</p>
        <div className="filters-grid catalog-filters-grid">
          <label>
            人群分组
            <select value={filters.group_code} onChange={(e) => setFilters({ ...filters, group_code: e.target.value })}>
              <option value="">全部</option>
              {groupCodes.map((value) => (
                <option key={value} value={value}>
                  {groupNames.get(value) || humanizeCode(value)}
                </option>
              ))}
            </select>
          </label>
          <label>
            组织
            <select value={filters.tissue} onChange={(e) => setFilters({ ...filters, tissue: e.target.value })}>
              <option value="">全部</option>
              {options.tissues.map((value) => (
                <option key={value} value={value}>
                  {localizeText(value)}
                </option>
              ))}
            </select>
          </label>
          <label>
            条件
            <select value={filters.condition} onChange={(e) => setFilters({ ...filters, condition: e.target.value })}>
              <option value="">全部</option>
              {options.conditions.map((value) => (
                <option key={value} value={value}>
                  {localizeText(value)}
                </option>
              ))}
            </select>
          </label>
          <label>
            物种
            <select value={filters.species} onChange={(e) => setFilters({ ...filters, species: e.target.value })}>
              <option value="">全部</option>
              {options.species.map((value) => (
                <option key={value} value={value}>
                  {localizeText(value)}
                </option>
              ))}
            </select>
          </label>
          <div className="filter-note">
            <strong>{formatCount(visibleSummary.total)}</strong>
            <span>可见样本</span>
          </div>
        </div>
      </div>

      <div className="section-head">
        <div>
          <p className="eyebrow">分组目录</p>
          <h3>按人群分组浏览样本</h3>
        </div>
        <p className="section-copy">打开样本可查看其资产和元数据；若存在已索引的 h5ad 资产，也可直接进入 RNA-seq 行级检索。</p>
      </div>

      {catalogLoading && !error ? (
        <div className="card empty-state">正在加载样本目录...</div>
      ) : (
        <div className="group-sections">
          {overviewGroups.map((group) => (
            <GroupSection group={group} key={group.groupCode} samples={filteredGroups.get(group.groupCode) || []} />
          ))}
        </div>
      )}

      <div className="card table-card">
        <div className="section-head compact-head">
          <div>
            <p className="eyebrow">配额表</p>
            <h3>人群分组覆盖审计</h3>
          </div>
          <p className="section-copy">该表始终保持全局统计，不会随样本级筛选而变化。</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>分组</th>
                <th>RNA-seq</th>
                <th>bulk</th>
                <th>FASTQ</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {quotaRows.map((group) => (
                <tr key={group.group_code}>
                  <td>{group.group_name}</td>
                  <td>
                    {group.single_cell_sample_count}/{group.min_single_cell_samples}
                  </td>
                  <td>
                    {group.bulk_sample_count}/{group.min_bulk_samples}
                  </td>
                  <td>{group.fastq_sample_count}</td>
                  <td>{statusLabel(group.single_cell_ok, group.bulk_ok)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function SampleDetailPage() {
  const { sampleId } = useParams();
  const navigate = useNavigate();
  const [sample, setSample] = useState(null);
  const [embedding, setEmbedding] = useState(null);
  const [error, setError] = useState("");
  const [embeddingError, setEmbeddingError] = useState("");

  useEffect(() => {
    api(`/samples/${sampleId}`)
      .then((data) => {
        setSample(data);
        setError("");
        if (data.has_single_cell) {
          return api(`/samples/${sampleId}/embedding`)
            .then((embeddingData) => {
              setEmbedding(embeddingData);
              setEmbeddingError("");
            })
            .catch((err) => {
              setEmbedding(null);
              setEmbeddingError(err.message);
            });
        }
        setEmbedding(null);
        setEmbeddingError("");
        return null;
      })
      .catch((err) => setError(err.message));
  }, [sampleId]);

  if (error) return <p className="error">{error}</p>;
  if (!sample) return <p>正在加载样本...</p>;

  const tags = detailTags(sample);
  const modalitySummary = formatModalities(sample.modalities, ", ");
  const assetsByModality = sample.assets.reduce((accumulator, asset) => {
    accumulator[asset.modality] = accumulator[asset.modality] || [];
    accumulator[asset.modality].push(asset);
    return accumulator;
  }, {});

  return (
    <section className="page-section">
      <header className="hero card detail-hero">
        <div className="hero-copy">
          <p className="eyebrow">样本详情</p>
          <h2>{titleForSample(sample)}</h2>
          <p>{localizeText(sample.description) || "暂无描述。"}</p>
          <TagList tags={tags} accent="bright" />
        </div>
        <div className="hero-actions detail-hero-actions">
          <div className="detail-hero-stats">
            <div>
              <span>样本 ID</span>
              <strong>{sample.sample_id}</strong>
            </div>
            <div>
              <span>人群分组</span>
              <strong>{sample.group.group_name || GROUP_NAME_FALLBACKS[sample.group.group_code] || sample.group.group_code}</strong>
            </div>
            <div>
              <span>已索引行</span>
              <strong>{formatCount(sample.single_cell_cell_count)}</strong>
            </div>
          </div>
          {sample.has_single_cell ? (
            <button onClick={() => navigate(`/single-cell?sample_id=${sample.sample_id}`)} type="button">
              打开 RNA-seq 检索
            </button>
          ) : null}
        </div>
      </header>

      <div className="detail-grid">
        <div className="card narrative-card">
          <h3>样本概览</h3>
          <p>
            该样本属于 <strong>{sample.group.group_name}</strong>，系统内标识为 <strong>{sample.sample_code}</strong>。
            当前提供的资产类型为 <strong>{modalitySummary}</strong>。
          </p>
          <p>
            当前模型以样本为中心管理文件，并仅为 RNA-seq h5ad 资产保留行级索引访问能力。
          </p>
          <div className="info-block">
            <span>数据类型</span>
            <code>{modalitySummary}</code>
          </div>
        </div>

        <div className="card">
          <h3>资产</h3>
          {MODALITY_ORDER.map((modality) => (
            <div className="download-group" key={modality}>
              <span className="download-kicker">{modalityLabel(modality)}</span>
              {assetsByModality[modality]?.length ? (
                <div className="download-list">
                  {assetsByModality[modality].map((asset) => (
                    <a
                      className="download-link"
                      href={`${API_BASE_URL}${asset.download_url}`}
                      key={asset.asset_id}
                      download={asset.file_name}
                    >
                      <strong>{asset.file_name}</strong>
                      <span>{asset.file_format}</span>
                      <em>{formatBytes(asset.size_bytes)}</em>
                    </a>
                  ))}
                </div>
              ) : (
                <p className="download-empty">该样本未关联 {modalityLabel(modality)} 资产。</p>
              )}
            </div>
          ))}
        </div>

        <div className="card">
          <h3>元数据</h3>
          <dl className="meta-list">
            <div>
              <dt>样本代号</dt>
              <dd>{sample.sample_code}</dd>
            </div>
            <div>
              <dt>分组</dt>
              <dd>{sample.group.group_name}</dd>
            </div>
            <div>
              <dt>物种</dt>
              <dd>{localizeText(sample.species) || "-"}</dd>
            </div>
            <div>
              <dt>组织</dt>
              <dd>{localizeText(sample.tissue) || "-"}</dd>
            </div>
            <div>
              <dt>条件</dt>
              <dd>{localizeText(sample.condition) || "-"}</dd>
            </div>
            <div>
              <dt>研究 ID</dt>
              <dd>{sample.study_id || "-"}</dd>
            </div>
            <div>
              <dt>受试者 ID</dt>
              <dd>{sample.subject_id || "-"}</dd>
            </div>
          </dl>
        </div>
      </div>

      {sample.has_single_cell ? <EmbeddingPanel embedding={embedding} error={embeddingError} /> : null}
    </section>
  );
}

function SingleCellQuery() {
  const location = useLocation();
  const search = new URLSearchParams(location.search);
  const [filters, setFilters] = useState({
    cell_type: search.get("cell_type") || "",
    tissue: search.get("tissue") || "",
    condition: search.get("condition") || "",
    group_code: search.get("group_code") || "",
    sample_id: search.get("sample_id") || "",
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
      const data = await api(`/single-cell/cells?${params.toString()}`);
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
        (entry) => entry.asset_id === item.asset_id && entry.obs_index === item.obs_index
      );
      if (exists) {
        return current.filter(
          (entry) => !(entry.asset_id === item.asset_id && entry.obs_index === item.obs_index)
        );
      }
      if (current.length > 0 && current[0].asset_id !== item.asset_id) {
        return [item];
      }
      return [...current, item];
    });
  }

  async function loadPreview() {
    if (selected.length === 0) return;
    try {
      const data = await api("/single-cell/data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          asset_id: selected[0].asset_id,
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
    <section className="page-section">
      <header className="hero card query-hero">
        <div className="hero-copy">
          <p className="eyebrow">RNA-seq 检索</p>
          <h2>检索各样本 RNA-seq 资产中的已索引行</h2>
          <p>只有拥有 RNA-seq h5ad 资产的样本才能参与行级检索和懒加载矩阵预览。</p>
        </div>
        <div className="hero-stats query-stats">
          <div>
            <strong>{formatCount(results.length)}</strong>
            <span>匹配行数</span>
          </div>
          <div>
            <strong>{formatCount(selected.length)}</strong>
            <span>已选行数</span>
          </div>
        </div>
      </header>

      <div className="card filters-card">
        <div className="filters-head">
          <div>
            <p className="eyebrow">检索条件</p>
            <h3>筛选 RNA-seq 索引</h3>
          </div>
        </div>
        <div className="filters-grid query-filters-grid">
          <label>
            细胞类型
            <input
              value={filters.cell_type}
              placeholder="T 细胞"
              onChange={(e) => setFilters({ ...filters, cell_type: e.target.value })}
            />
          </label>
          <label>
            组织
            <input
              value={filters.tissue}
              placeholder="PBMC"
              onChange={(e) => setFilters({ ...filters, tissue: e.target.value })}
            />
          </label>
          <label>
            条件
            <input
              value={filters.condition}
              placeholder="对照"
              onChange={(e) => setFilters({ ...filters, condition: e.target.value })}
            />
          </label>
          <label>
            分组代码
            <input
              value={filters.group_code}
              placeholder="plain_low_altitude"
              onChange={(e) => setFilters({ ...filters, group_code: e.target.value })}
            />
          </label>
          <label>
            样本 ID
            <input
              value={filters.sample_id}
              placeholder="可选"
              onChange={(e) => setFilters({ ...filters, sample_id: e.target.value })}
            />
          </label>
          <div className="query-actions">
            <button onClick={() => runQuery()} type="button">
              执行检索
            </button>
            <button
              className="secondary-button"
              onClick={() => {
                const cleared = { cell_type: "", tissue: "", condition: "", group_code: "", sample_id: "" };
                setFilters(cleared);
                runQuery(cleared);
              }}
              type="button"
            >
              重置
            </button>
          </div>
        </div>
      </div>

      {selected.length > 0 ? (
        <div className="selection-bar">
          <span>
            已从 <strong>{selected[0].sample_code}</strong> 选择 {selected.length} 行
          </span>
          <button onClick={loadPreview}>预览数据</button>
        </div>
      ) : null}

      {error ? <p className="error">{error}</p> : null}

      <div className="card table-card">
        <div className="section-head compact-head">
          <div>
            <p className="eyebrow">结果</p>
            <h3>已索引 RNA-seq 行</h3>
          </div>
          <p className="section-copy">从同一个资产中选择若干行后，可预览底层 h5ad 文件中的表达值。</p>
        </div>
        {results.length === 0 ? (
          <div className="empty-state">当前检索条件下没有匹配的已索引行。</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>选择</th>
                  <th>样本</th>
                  <th>分组</th>
                  <th>Obs 索引</th>
                  <th>条码</th>
                  <th>细胞类型</th>
                  <th>聚类</th>
                </tr>
              </thead>
              <tbody>
                {results.map((row) => {
                  const checked = selected.some(
                    (item) => item.asset_id === row.asset_id && item.obs_index === row.obs_index
                  );
                  return (
                    <tr key={`${row.asset_id}:${row.obs_index}`}>
                      <td>
                        <input type="checkbox" checked={checked} onChange={() => toggleSelection(row)} />
                      </td>
                      <td>{row.sample_code}</td>
                      <td>{GROUP_NAME_FALLBACKS[row.group_code] || row.group_code}</td>
                      <td>{row.obs_index}</td>
                      <td>{row.sample_barcode || "-"}</td>
                      <td>{localizeText(row.cell_type) || "-"}</td>
                      <td>{row.cluster || "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
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
    <section className="card table-card">
      <div className="section-head compact-head">
        <div>
          <p className="eyebrow">预览</p>
          <h3>数据预览</h3>
        </div>
        <p className="section-copy">这里展示所选行在源 `.h5ad` 文件中的前六个特征。</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Obs 索引</th>
              <th>条码</th>
              <th>细胞类型</th>
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
                <td>{localizeText(row.obs.cell_type) || "-"}</td>
                {row.values.map((value, index) => (
                  <td key={`${row.cell}:${genes[index]}`}>{value.toFixed(1)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EmbeddingPanel({ embedding, error }) {
  if (error) {
    return (
      <section className="card embedding-card">
        <h3>嵌入图</h3>
        <p className="error">{error}</p>
      </section>
    );
  }

  if (!embedding) {
    return (
      <section className="card embedding-card">
        <h3>嵌入图</h3>
        <p>正在加载嵌入图...</p>
      </section>
    );
  }

  const basisLabel = embedding.basis === "pca" ? "PCA" : "UMAP";

  return (
    <section className="card embedding-card">
      <div className="embedding-head">
        <div>
          <h3>{basisLabel} 概览</h3>
          <p>
            {embedding.returned_points > 0
              ? `已显示 ${embedding.total_points} 行中的 ${embedding.returned_points} 行${embedding.is_sampled ? "（采样）" : ""}。`
              : "该样本没有可用的嵌入坐标。"}
          </p>
        </div>
        <span className="metric-pill">{basisLabel}</span>
      </div>
      {embedding.points.length > 0 ? (
        <ScatterPlot points={embedding.points} basis={basisLabel} />
      ) : (
        <div className="empty-state">
          可用嵌入：{embedding.available_bases.length ? embedding.available_bases.join(", ") : "无"}
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
  const labels = [...new Set(points.map((point) => point.label || "未知"))].slice(0, 12);
  const palette = ["#145a46", "#b35c1e", "#315f9c", "#8a4b91", "#2b7a78", "#b23a48", "#6a7d23", "#6b5b95"];
  const colorFor = (label) => palette[Math.max(labels.indexOf(label), 0) % palette.length];
  const scaleX = (value) => padding + ((value - minX) / xSpan) * (width - padding * 2);
  const scaleY = (value) => height - padding - ((value - minY) / ySpan) * (height - padding * 2);

  return (
    <div className="embedding-plot-wrap">
      <svg className="embedding-plot" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${basis} 散点图`}>
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} />
        {points.map((point) => {
          const label = point.label || "未知";
          return (
            <circle
              key={`${point.obs_index}:${point.x}:${point.y}`}
              cx={scaleX(point.x)}
              cy={scaleY(point.y)}
              r="4"
              fill={colorFor(label)}
            >
              <title>{`${localizeText(label)} | ${point.sample_id || "无样本"} | 第 ${point.obs_index} 行`}</title>
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
            {localizeText(label)}
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
        <Route path="/" element={<SampleBrowser />} />
        <Route path="/samples/:sampleId" element={<SampleDetailPage />} />
        <Route path="/single-cell" element={<SingleCellQuery />} />
      </Routes>
    </Layout>
  );
}
