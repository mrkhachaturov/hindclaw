use colored::*;

// HindClaw gradient: teal (#00BCD4) -> darker teal (#00838F)
const GRADIENT_START: (u8, u8, u8) = (0, 188, 212);
const GRADIENT_END: (u8, u8, u8) = (0, 131, 143);

fn interpolate_color(start: (u8, u8, u8), end: (u8, u8, u8), t: f32) -> (u8, u8, u8) {
    (
        (start.0 as f32 + (end.0 as f32 - start.0 as f32) * t) as u8,
        (start.1 as f32 + (end.1 as f32 - start.1 as f32) * t) as u8,
        (start.2 as f32 + (end.2 as f32 - start.2 as f32) * t) as u8,
    )
}

#[allow(dead_code)]
pub fn gradient(text: &str, t: f32) -> String {
    let (r, g, b) = interpolate_color(GRADIENT_START, GRADIENT_END, t);
    format!("\x1b[38;2;{};{};{}m{}\x1b[0m", r, g, b, text)
}

pub fn gradient_text(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let len = chars.len();
    if len == 0 { return String::new(); }
    let mut result = String::new();
    for (i, ch) in chars.iter().enumerate() {
        if *ch == ' ' {
            result.push(' ');
        } else {
            let t = i as f32 / (len - 1).max(1) as f32;
            let (r, g, b) = interpolate_color(GRADIENT_START, GRADIENT_END, t);
            result.push_str(&format!("\x1b[38;2;{};{};{}m{}", r, g, b, ch));
        }
    }
    result.push_str("\x1b[0m");
    result
}

pub fn dim(text: &str) -> String {
    format!("\x1b[38;2;128;128;128m{}\x1b[0m", text)
}

#[allow(dead_code)]
pub fn print_section_header(title: &str) {
    println!();
    println!("{}", gradient_text(&format!("━━━ {} ━━━", title)));
    println!();
}

/// Print a simple key-value pair with aligned colons
#[allow(dead_code)]
pub fn print_kv(key: &str, value: &str) {
    println!("  {:<16}{}", format!("{}:", key).bold(), value);
}

/// Print a table with headers and rows
pub fn print_table(headers: &[&str], rows: &[Vec<String>]) {
    if rows.is_empty() {
        println!("  {}", dim("(none)"));
        return;
    }

    // Calculate column widths
    let mut widths: Vec<usize> = headers.iter().map(|h| h.len()).collect();
    for row in rows {
        for (i, cell) in row.iter().enumerate() {
            if i < widths.len() {
                widths[i] = widths[i].max(cell.len());
            }
        }
    }

    // Print header
    let header_line: String = headers.iter().enumerate()
        .map(|(i, h)| format!("{:<width$}", h, width = widths[i] + 2))
        .collect();
    println!("  {}", header_line.bold());

    // Print rows
    for row in rows {
        let line: String = row.iter().enumerate()
            .map(|(i, cell)| format!("{:<width$}", cell, width = widths.get(i).copied().unwrap_or(0) + 2))
            .collect();
        println!("  {}", line);
    }
}

pub fn print_success(msg: &str) {
    println!("  {} {}", "✓".green(), msg);
}

#[allow(dead_code)]
pub fn print_warning(msg: &str) {
    eprintln!("  {} {}", "⚠".yellow(), msg);
}

#[allow(dead_code)]
pub fn print_error(msg: &str) {
    eprintln!("  {} {}", "✗".red(), msg);
}
