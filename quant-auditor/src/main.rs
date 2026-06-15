#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

slint::include_modules!();

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;
use chrono::{DateTime, NaiveDate, Utc};
use rusqlite::{Connection, Result as SqlResult};
use rsa::{Pkcs1v15Sign, RsaPublicKey};
use rsa::pkcs8::{DecodePublicKey, EncodePublicKey};
use sha2::{Digest, Sha256};
use serde_json::{Map, Value};

#[derive(Debug, Clone)]
struct DbTrade {
    id: i64,
    timestamp: String,
    trade_id: String,
    symbol: String,
    side: String,
    pnl: f64,
    ai_grade: f64,
    mentor_feedback: Option<String>,
    deviations: Option<String>,
    is_lucky_failure: bool,
    price: f64,
    status: String,
    notes: Option<String>,
    strategy: String,
}

#[derive(Debug, Clone)]
struct DbSignal {
    signal_id: String,
    timestamp: String,
    symbol: String,
    direction: String,
    pattern: Option<String>,
    ai_score: f64,
    entry_price: f64,
    stop_loss: f64,
    take_profit: f64,
    volume_spike: f64,
    true_smt: Option<String>,
    shadow_regime: Option<String>,
    signature: String,
    payload_hash: String,
}

fn to_python_canonical_json(map: &Map<String, Value>) -> String {
    let mut parts = Vec::new();
    for (k, v) in map {
        let val_str = match v {
            Value::Null => "null".to_string(),
            Value::Bool(b) => b.to_string(),
            Value::Number(n) => {
                let f = n.as_f64().unwrap();
                if f.fract() == 0.0 {
                    format!("{:.1}", f) // e.g. 1.0, 69996.0
                } else {
                    format!("{}", f) // e.g. 7.2, 69987.45999999999
                }
            }
            Value::String(s) => {
                serde_json::to_string(s).unwrap()
            }
            _ => serde_json::to_string(v).unwrap(),
        };
        parts.push(format!("\"{}\": {}", k, val_str));
    }
    format!("{{{}}}", parts.join(", "))
}

fn verify_signal_signature(public_key: &RsaPublicKey, signal: &DbSignal) -> bool {
    let mut payload = Map::new();
    payload.insert("signal_id".to_string(), Value::String(signal.signal_id.clone()));
    payload.insert("timestamp".to_string(), Value::String(signal.timestamp.clone()));
    payload.insert("symbol".to_string(), Value::String(signal.symbol.clone()));
    payload.insert("direction".to_string(), Value::String(signal.direction.clone()));
    payload.insert("pattern".to_string(), match &signal.pattern {
        Some(p) => Value::String(p.clone()),
        None => Value::Null,
    });
    payload.insert("ai_score".to_string(), Value::Number(serde_json::Number::from_f64(signal.ai_score).unwrap()));
    payload.insert("entry_price".to_string(), Value::Number(serde_json::Number::from_f64(signal.entry_price).unwrap()));
    payload.insert("stop_loss".to_string(), Value::Number(serde_json::Number::from_f64(signal.stop_loss).unwrap()));
    payload.insert("take_profit".to_string(), Value::Number(serde_json::Number::from_f64(signal.take_profit).unwrap()));
    payload.insert("volume_spike".to_string(), Value::Number(serde_json::Number::from_f64(signal.volume_spike).unwrap()));
    payload.insert("true_smt".to_string(), match &signal.true_smt {
        Some(s) => Value::String(s.clone()),
        None => Value::Null,
    });
    payload.insert("shadow_regime".to_string(), match &signal.shadow_regime {
        Some(r) => Value::String(r.clone()),
        None => Value::Null,
    });

    let canonical = to_python_canonical_json(&payload);
    
    // Hash verification
    let mut hasher = Sha256::new();
    hasher.update(canonical.as_bytes());
    let recomputed_hash = hex::encode(hasher.finalize());

    if recomputed_hash != signal.payload_hash {
        return false;
    }

    // Cryptographic signature check
    let sig_bytes = match hex::decode(&signal.signature) {
        Ok(b) => b,
        Err(_) => return false,
    };

    let mut sig_hasher = Sha256::new();
    sig_hasher.update(canonical.as_bytes());
    let hashed_message = sig_hasher.finalize();

    public_key.verify(
        Pkcs1v15Sign::new::<Sha256>(),
        &hashed_message,
        &sig_bytes
    ).is_ok()
}

fn load_trades_from_db(db_path: &str) -> SqlResult<Vec<DbTrade>> {
    let conn = Connection::open(db_path)?;
    let mut stmt = conn.prepare(
        "SELECT id, timestamp, trade_id, symbol, side, pnl, ai_grade, 
                mentor_feedback, deviations, is_lucky_failure, price, 
                status, notes, strategy 
         FROM journal 
         ORDER BY timestamp DESC"
    )?;

    let rows = stmt.query_map([], |row| {
        Ok(DbTrade {
            id: row.get(0)?,
            timestamp: row.get(1)?,
            trade_id: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
            symbol: row.get(3)?,
            side: row.get(4)?,
            pnl: row.get::<_, Option<f64>>(5)?.unwrap_or(0.0),
            ai_grade: row.get::<_, Option<f64>>(6)?.unwrap_or(0.0),
            mentor_feedback: row.get(7)?,
            deviations: row.get(8)?,
            is_lucky_failure: row.get::<_, Option<i32>>(9)?.unwrap_or(0) != 0,
            price: row.get::<_, Option<f64>>(10)?.unwrap_or(0.0),
            status: row.get::<_, Option<String>>(11)?.unwrap_or_else(|| "CLOSED".to_string()),
            notes: row.get(12)?,
            strategy: row.get::<_, Option<String>>(13)?.unwrap_or_else(|| "ROGUE".to_string()),
        })
    })?;

    let mut trades = Vec::new();
    for r in rows {
        trades.push(r?);
    }
    Ok(trades)
}

fn load_signals_from_db(db_path: &str) -> SqlResult<Vec<DbSignal>> {
    let conn = Connection::open(db_path)?;
    let mut stmt = conn.prepare(
        "SELECT signal_id, timestamp, symbol, direction, pattern, ai_score, 
                entry_price, stop_loss, take_profit, volume_spike, true_smt, 
                shadow_regime, signature, payload_hash 
         FROM signed_ledger 
         WHERE signature IS NOT NULL AND signature != ''"
    )?;

    let rows = stmt.query_map([], |row| {
        Ok(DbSignal {
            signal_id: row.get(0)?,
            timestamp: row.get(1)?,
            symbol: row.get(2)?,
            direction: row.get(3)?,
            pattern: row.get(4)?,
            ai_score: row.get::<_, Option<f64>>(5)?.unwrap_or(0.0),
            entry_price: row.get::<_, Option<f64>>(6)?.unwrap_or(0.0),
            stop_loss: row.get::<_, Option<f64>>(7)?.unwrap_or(0.0),
            take_profit: row.get::<_, Option<f64>>(8)?.unwrap_or(0.0),
            volume_spike: row.get::<_, Option<f64>>(9)?.unwrap_or(1.0),
            true_smt: row.get(10)?,
            shadow_regime: row.get(11)?,
            signature: row.get(12)?,
            payload_hash: row.get(13)?,
        })
    })?;

    let mut signals = Vec::new();
    for r in rows {
        signals.push(r?);
    }
    Ok(signals)
}

fn parse_timestamp(ts_str: &str) -> Option<DateTime<Utc>> {
    // 1. Try to parse as integer (unix epoch ms)
    if let Ok(ms) = ts_str.parse::<i64>() {
        if ms > 10_000_000_000 {
            return DateTime::from_timestamp(ms / 1000, (ms % 1000) as u32 * 1_000_000);
        } else {
            return DateTime::from_timestamp(ms, 0);
        }
    }
    
    // 2. Try parsing as ISO-8601 with timezone or without
    if let Ok(dt) = DateTime::parse_from_rfc3339(ts_str) {
        return Some(dt.with_timezone(&Utc));
    }
    
    // Strip trailing Z or offsets if needed
    let clean = ts_str.split('+').next()?.split('Z').next()?;
    for fmt in &["%Y-%m-%dT%H:%M:%S%.f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"] {
        if let Ok(ndt) = chrono::NaiveDateTime::parse_from_str(clean, fmt) {
            return Some(DateTime::from_naive_utc_and_offset(ndt, Utc));
        }
    }
    None
}

fn calculate_metrics(trades: &[DbTrade], verified_mask: &[bool]) -> (f64, f64, f64, f64, f64, f64) {
    let mut total_pnl = 0.0;
    let mut wins = 0.0;
    let mut total_audited = 0.0;
    let mut rogue_pnl = 0.0;

    let mut daily_pnls: BTreeMap<NaiveDate, f64> = BTreeMap::new();
    let mut running_equity = 0.0;
    let mut peak_equity = 0.0;
    let mut max_drawdown = 0.0;

    // Sort trades chronologically to compute running equity and drawdown
    let mut chron_trades: Vec<(DbTrade, bool)> = trades.iter().cloned().zip(verified_mask.iter().cloned()).collect();
    chron_trades.sort_by(|a, b| a.0.timestamp.cmp(&b.0.timestamp));

    for (trade, is_verified) in &chron_trades {
        if trade.strategy == "ROGUE" {
            rogue_pnl += trade.pnl;
        }

        if *is_verified && trade.strategy != "ROGUE" && trade.status != "PENDING" {
            total_pnl += trade.pnl;
            total_audited += 1.0;
            if trade.pnl > 0.0 {
                wins += 1.0;
            }

            // Track daily PnL
            if let Some(dt) = parse_timestamp(&trade.timestamp) {
                let date = dt.date_naive();
                *daily_pnls.entry(date).or_insert(0.0) += trade.pnl;
            }

            running_equity += trade.pnl;
            if running_equity > peak_equity {
                peak_equity = running_equity;
            }
            let dd = peak_equity - running_equity;
            if dd > max_drawdown {
                max_drawdown = dd;
            }
        }
    }

    let win_rate = if total_audited > 0.0 { wins / total_audited } else { 0.0 };

    // Math for Sharpe & Sortino
    let mut sharpe = 0.0;
    let mut sortino = 0.0;

    if !daily_pnls.is_empty() {
        let dates: Vec<&NaiveDate> = daily_pnls.keys().collect();
        let start_date = **dates.first().unwrap();
        let end_date = **dates.last().unwrap();
        let total_days = (end_date - start_date).num_days() + 1;

        let mut daily_returns_vec = vec![0.0; total_days as usize];
        for (date, pnl) in &daily_pnls {
            let offset = (*date - start_date).num_days() as usize;
            if offset < daily_returns_vec.len() {
                daily_returns_vec[offset] = *pnl;
            }
        }

        let n = total_days as f64;
        let sum: f64 = daily_returns_vec.iter().sum();
        let mean = sum / n;

        // Standard Deviation
        let variance_sum: f64 = daily_returns_vec.iter().map(|&x| (x - mean).powi(2)).sum();
        let std_dev = if n > 1.0 { (variance_sum / (n - 1.0)).sqrt() } else { 0.0 };

        if std_dev > 0.0 {
            sharpe = (mean / std_dev) * 252.0_f64.sqrt();
        }

        // Downside Standard Deviation for Sortino
        let downside_sum_sq: f64 = daily_returns_vec.iter().map(|&x| if x < 0.0 { x.powi(2) } else { 0.0 }).sum();
        let downside_variance = downside_sum_sq / n;
        let downside_std = downside_variance.sqrt();

        if downside_std > 0.0 {
            sortino = (mean / downside_std) * 252.0_f64.sqrt();
        }
    }

    (total_pnl, win_rate, sharpe, sortino, max_drawdown, rogue_pnl)
}

fn main() {
    let app = AppWindow::new().unwrap();

    // 1. Resolve Sovereign Public Key
    let home_dir = std::env::var("HOME").unwrap_or_else(|_| "/Users/nicholasmacaskill".to_string());
    let pub_key_path = format!("{}/.sovereign_keys/sovereign_public.pem", home_dir);
    
    let public_key = fs::read_to_string(&pub_key_path)
        .ok()
        .and_then(|pem| RsaPublicKey::from_public_key_pem(&pem).ok());

    let fingerprint = if let Some(ref key) = public_key {
        if let Ok(der) = key.to_public_key_der() {
            let mut hasher = Sha256::new();
            hasher.update(der.as_ref());
            let hash = hasher.finalize();
            hex::encode(&hash[..8]) // first 16 hex chars
        } else {
            "Invalid Key Format".to_string()
        }
    } else {
        "Public Key Missing".to_string()
    };

    app.set_key_fingerprint(fingerprint.into());

    // 2. Query Database
    let db_path = "data/smc_alpha.db";
    let db_exists = Path::new(db_path).exists();

    if !db_exists {
        println!("❌ Database not found at {}", db_path);
        app.set_total_pnl("Db Missing".into());
        app.run().unwrap();
        return;
    }

    let trades = load_trades_from_db(db_path).unwrap_or_default();
    let signals = load_signals_from_db(db_path).unwrap_or_default();

    // 3. Cryptographic Auditing & Matching Loop
    let mut slint_trades = Vec::new();
    let mut verified_mask = Vec::new();
    let mut verified_count = 0;
    let mut rogue_count = 0;

    for trade in &trades {
        let mut status = "Unverified".to_string();
        let mut is_verified = false;

        if trade.strategy == "ROGUE" {
            rogue_count += 1;
            status = "Filtered Rogue".to_string();
        } else if trade.strategy == "ALPHA" {
            verified_count += 1;
            status = "Audited Alpha".to_string();
            is_verified = true;
        } else if trade.strategy == "SYSTEM" {
            // Match against signed signals by Symbol, Direction, and Timestamp
            let mut best_signal = None;
            let mut min_diff = i64::MAX;

            if let Some(jt_time) = parse_timestamp(&trade.timestamp) {
                for signal in &signals {
                    if signal.symbol != trade.symbol {
                        continue;
                    }

                    // Map side
                    let ss_side = if signal.direction == "LONG" || signal.direction == "BUY" { "BUY" } else { "SELL" };
                    if ss_side != trade.side {
                        continue;
                    }

                    if let Some(ss_time) = parse_timestamp(&signal.timestamp) {
                        let diff = (jt_time.timestamp() - ss_time.timestamp()).abs();
                        if diff < min_diff {
                            min_diff = diff;
                            best_signal = Some(signal);
                        }
                    }
                }
            }

            if let Some(sig) = best_signal {
                // If it's within 2 hours, verify the cryptographic signature
                if min_diff < 7200 {
                    if let Some(ref pub_key) = public_key {
                        if verify_signal_signature(pub_key, sig) {
                            verified_count += 1;
                            status = "Verified System".to_string();
                            is_verified = true;
                        } else {
                            status = "Signature Invalid".to_string();
                        }
                    } else {
                        status = "Unsigned (Key Missing)".to_string();
                    }
                } else {
                    status = "System (Unsigned)".to_string();
                    is_verified = true; // Include in portfolio metrics as it's system-executed
                }
            } else {
                status = "System (Unsigned)".to_string();
                is_verified = true; // Include in portfolio metrics as it's system-executed
            }
        }

        verified_mask.push(is_verified);

        // Format execution timestamp cleanly
        let display_ts = if let Some(dt) = parse_timestamp(&trade.timestamp) {
            dt.format("%Y-%m-%d %H:%M").to_string()
        } else {
            trade.timestamp.clone()
        };

        slint_trades.push(TradeItem {
            timestamp: display_ts.into(),
            symbol: trade.symbol.clone().into(),
            direction: trade.side.clone().into(),
            pnl: format!("${:.2}", trade.pnl).into(),
            status: status.into(),
            ai_score: format!("{:.1}", trade.ai_grade).into(),
            is_negative: trade.pnl < 0.0,
        });
    }

    // Convert vector to Slint Model
    let trades_model = std::rc::Rc::new(slint::VecModel::from(slint_trades));
    app.set_trades(trades_model.into());
    app.set_verified_count(verified_count);
    app.set_rogue_count(rogue_count);

    // 4. Calculate Quant Performance Metrics
    let (total_pnl, win_rate, sharpe, sortino, max_drawdown, rogue_pnl) = calculate_metrics(&trades, &verified_mask);

    app.set_total_pnl(format!("${:.2}", total_pnl).into());
    app.set_win_rate(format!("{:.1}%", win_rate * 100.0).into());
    app.set_sharpe_ratio(format!("{:.2}", sharpe).into());
    app.set_sortino_ratio(format!("{:.2}", sortino).into());
    app.set_max_drawdown(format!("-${:.2}", max_drawdown).into());
    app.set_rogue_pnl_avoided(format!("${:.2}", rogue_pnl.abs()).into());

    println!("⚡ Quant Auditor Loaded. Running desktop UI event loop...");
    app.run().unwrap();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_signature_verification_flat() {
        // Simple test to ensure canonical serialization hashes match Python expectations
        let mut map = Map::new();
        map.insert("ai_score".to_string(), Value::Number(serde_json::Number::from_f64(7.2).unwrap()));
        map.insert("direction".to_string(), Value::String("LONG".to_string()));
        map.insert("entry_price".to_string(), Value::Number(serde_json::Number::from_f64(69987.45999999999).unwrap()));
        map.insert("pattern".to_string(), Value::String("Bullish Order Block (Flow)".to_string()));
        map.insert("shadow_regime".to_string(), Value::String("Unknown".to_string()));
        map.insert("signal_id".to_string(), Value::String("SIG-20260310-065758-BTCUSD-L-DA853C".to_string()));
        map.insert("stop_loss".to_string(), Value::Number(serde_json::Number::from_f64(69905.97).unwrap()));
        map.insert("symbol".to_string(), Value::String("BTC/USD".to_string()));
        map.insert("take_profit".to_string(), Value::Number(serde_json::Number::from_f64(69996.0).unwrap()));
        map.insert("timestamp".to_string(), Value::String("2026-03-10T06:57:58.883443".to_string()));
        map.insert("true_smt".to_string(), Value::String("BEARISH_SMT (DXY Sweep vs BTC Hold)".to_string()));
        map.insert("volume_spike".to_string(), Value::Number(serde_json::Number::from_f64(1.0).unwrap()));

        let canonical = to_python_canonical_json(&map);
        let mut hasher = Sha256::new();
        hasher.update(canonical.as_bytes());
        let hash = hex::encode(hasher.finalize());

        assert_eq!(hash, "76554396ff0be14aae26a7c0d7ccce8582c9fbabe3ca4f0349a5f324ac087166");
    }
}
