import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://lvgmstnjcznggbqcgwnk.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx2Z21zdG5qY3puZ2dicWNnd25rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg0MDg4NjksImV4cCI6MjA4Mzk4NDg2OX0.uINR6vRQ8LV7m5tZJ23Ii7J3DVImx9cA5GP7vESBv7U'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Database types (auto-generated from schema)
export type JournalEntry = {
    id: number
    timestamp: string
    trade_id: string
    symbol: string
    side: string
    pnl: number
    ai_grade: number
    mentor_feedback: string | null
    deviations: string | null
    is_lucky_failure: boolean
    price: number
    status: string
    notes: string | null
    strategy: string
}

export type Scan = {
    id: number
    timestamp: string
    symbol: string
    timeframe: string | null
    pattern: string
    bias: string
    ai_score: number
    ai_reasoning: string | null
    status: string
    verdict: string
    shadow_regime: string
    shadow_multiplier: number
}

export type PropAudit = {
    id: number
    timestamp: string
    firm_name: string
    risk_score: number
    traps: any[]
    verdict: string
    recommendation: string
}
