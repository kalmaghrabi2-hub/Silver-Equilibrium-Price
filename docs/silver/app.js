const byId = (id) => document.getElementById(id);
const setText = (id, value) => { const el = byId(id); if (el) el.textContent = value; };
const fmt = (value, digits = 2) => Number.isFinite(Number(value))
  ? new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value))
  : '—';
const money = (value) => Number.isFinite(Number(value)) ? '$' + fmt(value, 2) + '/oz' : '—';
const percent = (value) => Number.isFinite(Number(value)) ? fmt(value, 2) + '%' : '—';
const moz = (value) => Number.isFinite(Number(value)) ? fmt(value, 1) + ' Moz' : '—';
const gateClass = (value) => value === 'PASS' ? 'green' : ((value === 'FAIL' || value === 'STALE') ? 'red' : 'yellow');

fetch('./data/latest.json?ts=' + Date.now(), { cache: 'no-store' })
  .then((response) => response.json())
  .then((data) => {
    setText('updated', data.generated_at_utc ? 'آخر تحديث آلي: ' + new Date(data.generated_at_utc).toLocaleString('ar-SA') : 'في انتظار أول تشغيل آلي');
    setText('status', data.model_status || '—');
    if (byId('status')) byId('status').className = data.model_status === 'VALID' ? 'green' : (data.model_status === 'UNAVAILABLE' ? 'red' : 'yellow');
    setText('quality', data.data_quality || '—');

    if (data.market) {
      setText('spot', money(data.market.usd_oz));
      setText('spotMeta', (data.market.provider || '') + ' · ' + (data.market.freshness_status || 'unknown') + (data.market.as_of ? ' · ' + data.market.as_of : ''));
    }

    const model = data.model;
    if (model) {
      setText('pstar', money(model.fundamental_p_star_usd_oz));
      setText('pstarMeta', (model.status || '') + ' · confidence ' + (model.confidence || ''));
      const gap = Number(model.market_vs_pstar_pct);
      setText('gap', (gap >= 0 ? '+' : '') + percent(gap));
      if (byId('gap')) byId('gap').className = gap >= 0 ? 'red' : 'green';
      setText('gapMeta', gap >= 0 ? 'السوق أعلى من السعر المتعادل' : 'السوق أقل من السعر المتعادل');
      setText('weeklyP', money(model.weekly_fair_value_usd_oz));

      const physical = model.physical_overlay || {};
      setText('physical', fmt(physical.multiplier, 5) + '×');
      setText('dsRatio', fmt(physical.demand_supply_ratio, 5));
      setText('eqExponent', fmt(physical.equilibrium_exponent, 6));
      setText('physicalGate', physical.physical_source_gate || '—');
      if (byId('physicalGate')) byId('physicalGate').className = gateClass(physical.physical_source_gate);
      setText('guardrail', model.guardrail_active ? 'YES' : 'NO');
      setText('physicalVintage', (physical.snapshot_year || '—') + ' · ' + (physical.vintage_type || '—'));
      setText('supply', moz(physical.total_supply_moz));
      setText('demand', moz(physical.total_demand_moz));
      setText('balance', moz(physical.market_balance_moz));
      if (byId('balance')) byId('balance').className = Number(physical.market_balance_moz) < 0 ? 'red' : 'green';
      setText('mine', moz(physical.mine_production_moz));
      setText('recycling', moz(physical.recycling_moz));
      setText('industrial', moz(physical.industrial_demand_moz));
      setText('coinbar', moz(physical.coin_net_bar_demand_moz));
      setText('etp', moz(physical.net_etp_investment_moz));
      setText('es', fmt(physical.elasticity_supply, 2));
      setText('ed', fmt(physical.elasticity_demand, 2));
    }

    const macro = data.macro || {};
    if (macro['GC=F']) setText('gold', money(macro['GC=F'].value) + ' · ' + macro['GC=F'].date);
    if (macro['DX-Y.NYB']) setText('usd', fmt(macro['DX-Y.NYB'].value, 2) + ' · ' + macro['DX-Y.NYB'].date);
    if (macro['^TNX']) setText('tnx', percent(macro['^TNX'].value) + ' · ' + macro['^TNX'].date);
    if (macro['^VIX']) setText('vix', fmt(macro['^VIX'].value, 2) + ' · ' + macro['^VIX'].date);
    if (macro['HG=F']) setText('copper', fmt(macro['HG=F'].value, 4) + ' · ' + macro['HG=F'].date);

    const calibration = data.calibration || {};
    const metrics = calibration.metrics || {};
    setText('wf', calibration.walk_forward_gate || 'PENDING');
    if (byId('wf')) byId('wf').className = gateClass(calibration.walk_forward_gate);
    setText('oos', metrics.walk_forward_n ?? '—');
    setText('r2', metrics.r2 ?? '—');
    setText('mape', metrics.mape_pct == null ? '—' : fmt(metrics.mape_pct, 2) + '%');
    setText('rmse', metrics.rmse_usd_oz == null ? '—' : money(metrics.rmse_usd_oz));
    setText('direction', metrics.direction_accuracy_pct == null ? '—' : percent(metrics.direction_accuracy_pct));

    if (byId('badge')) byId('badge').textContent = (data.model_status || 'PENDING') + ' · GOVERNANCE GATES ACTIVE';
  })
  .catch((error) => {
    setText('quality', 'LOAD ERROR');
    setText('status', 'UNAVAILABLE');
    console.error(error);
  });
