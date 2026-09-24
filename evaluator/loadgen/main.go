// Gerador de carga do diagnóstico de latência (RNF11, M16), executado no container cliente.
//
// Só biblioteca padrão. Lê os parâmetros em JSON pela entrada padrão e imprime o resultado
// em JSON. Malha fechada: Concurrency workers disparam requisições em sequência até
// completar Warmup+Requests; as Warmup primeiras não entram nas estatísticas. Cada
// resposta é validada contra o contrato; a latência de respostas inválidas ou com erro
// de transporte não entra nos percentis e é contada à parte.
//
// Operações:
//
//	seed      cria Requests links (sem medir) e devolve os códigos e as URLs
//	redirect  GET /{code} sobre os links semeados; válido = 302 com Location igual à url
//	create    POST /api/links sem alias; válido = 201 com objeto JSON e code string
//	visits    GET /api/links/{code} de cada código (sem medir); devolve a soma de visits
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net"
	"net/http"
	"os"
	"sort"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

type params struct {
	Host        string   `json:"host"`
	Port        int      `json:"port"`
	Op          string   `json:"op"`
	Concurrency int      `json:"concurrency"`
	Warmup      int      `json:"warmup"`
	Requests    int      `json:"requests"`
	Codes       []string `json:"codes"`
	URLs        []string `json:"urls"`
	TimeoutMs   int      `json:"timeout_ms"`
	Tag         string   `json:"tag"`
}

type result struct {
	Op             string         `json:"op"`
	Concurrency    int            `json:"concurrency"`
	Warmup         int            `json:"warmup"`
	Requests       int            `json:"requests"`
	Valid          int            `json:"valid"`
	WarmupValid    int            `json:"warmup_valid"`
	VisitsTotal    *int           `json:"visits_total,omitempty"`
	Invalid        int            `json:"invalid"`
	TransportErr   int            `json:"transport_errors"`
	ErrorRate      float64        `json:"error_rate"`
	WallSeconds    float64        `json:"wall_seconds"`
	ThroughputRPS  float64        `json:"throughput_valid_rps"`
	LatencyMs      map[string]any `json:"latency_ms"`
	Statuses       map[string]int `json:"statuses"`
	InvalidSamples []string       `json:"invalid_samples"`
	Codes          []string       `json:"codes,omitempty"`
	URLs           []string       `json:"urls,omitempty"`
}

type sample struct {
	ns     int64
	valid  bool
	status int
	note   string
	code   string
	visits int
}

func main() {
	var p params
	if err := json.NewDecoder(os.Stdin).Decode(&p); err != nil {
		fail("parâmetros inválidos: " + err.Error())
	}
	if p.Concurrency < 1 || p.Requests < 1 || p.Warmup < 0 {
		fail("concurrency e requests devem ser ≥ 1 e warmup ≥ 0")
	}
	if p.Op == "visits" {
		p.Requests = len(p.Codes)
	}
	if (p.Op == "redirect" || p.Op == "visits") && (len(p.Codes) == 0 || len(p.Codes) != len(p.URLs)) {
		fail("redirect exige codes e urls do mesmo tamanho")
	}
	timeout := time.Duration(p.TimeoutMs) * time.Millisecond
	transport := &http.Transport{
		DialContext:         (&net.Dialer{Timeout: timeout}).DialContext,
		MaxIdleConns:        p.Concurrency * 2,
		MaxIdleConnsPerHost: p.Concurrency * 2,
		DisableCompression:  true,
	}
	client := &http.Client{
		Transport: transport,
		Timeout:   timeout,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	base := "http://" + p.Host + ":" + strconv.Itoa(p.Port)
	total := p.Warmup + p.Requests
	samples := make([]sample, total)
	var next int64 = -1
	var measureStart, measureEnd atomic.Int64
	var wg sync.WaitGroup
	for w := 0; w < p.Concurrency; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				i := int(atomic.AddInt64(&next, 1))
				if i >= total {
					return
				}
				if i == p.Warmup {
					measureStart.Store(time.Now().UnixNano())
				}
				samples[i] = do(client, base, &p, i)
				measureEnd.Store(time.Now().UnixNano())
			}
		}()
	}
	wg.Wait()
	transport.CloseIdleConnections()

	r := result{Op: p.Op, Concurrency: p.Concurrency, Warmup: p.Warmup, Requests: p.Requests,
		Statuses: map[string]int{}, InvalidSamples: []string{}}
	var lat []float64
	for i, s := range samples {
		if p.Op == "seed" {
			if !s.valid {
				fail(fmt.Sprintf("criação da semente %d falhou: %s", i, s.note))
			}
			r.Codes = append(r.Codes, s.code)
			r.URLs = append(r.URLs, seedURL(p.Tag, i))
			continue
		}
		if p.Op == "visits" {
			if !s.valid {
				fail(fmt.Sprintf("consulta %d falhou: %s", i, s.note))
			}
			total := 0
			if r.VisitsTotal != nil {
				total = *r.VisitsTotal
			}
			total += s.visits
			r.VisitsTotal = &total
			continue
		}
		if i < p.Warmup {
			if s.valid {
				r.WarmupValid++
			}
			continue
		}
		key := strconv.Itoa(s.status)
		if s.status == 0 {
			key = "sem resposta"
		}
		r.Statuses[key]++
		switch {
		case s.valid:
			r.Valid++
			lat = append(lat, float64(s.ns)/1e6)
		case s.status == 0:
			r.TransportErr++
		default:
			r.Invalid++
		}
		if !s.valid && len(r.InvalidSamples) < 5 {
			r.InvalidSamples = append(r.InvalidSamples, s.note)
		}
	}
	if p.Op != "seed" && p.Op != "visits" {
		wall := float64(measureEnd.Load()-measureStart.Load()) / 1e9
		r.WallSeconds = round(wall, 3)
		if wall > 0 {
			r.ThroughputRPS = round(float64(r.Valid)/wall, 1)
		}
		r.ErrorRate = round(float64(r.Invalid+r.TransportErr)/float64(p.Requests), 6)
		r.LatencyMs = summarize(lat)
	}
	out, _ := json.Marshal(r)
	os.Stdout.Write(append(out, '\n'))
}

func seedURL(tag string, i int) string {
	return fmt.Sprintf("https://example.com/latencia/%s/%d?q=%d", tag, i, i)
}

func do(client *http.Client, base string, p *params, i int) sample {
	var req *http.Request
	var expectURL string
	switch p.Op {
	case "redirect":
		k := i % len(p.Codes)
		expectURL = p.URLs[k]
		req, _ = http.NewRequest("GET", base+"/"+p.Codes[k], nil)
	case "visits":
		req, _ = http.NewRequest("GET", base+"/api/links/"+p.Codes[i], nil)
	case "create", "seed":
		url := fmt.Sprintf("https://example.com/latencia/%s/c%d", p.Tag, i)
		if p.Op == "seed" {
			url = seedURL(p.Tag, i)
		}
		body, _ := json.Marshal(map[string]string{"url": url})
		req, _ = http.NewRequest("POST", base+"/api/links", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
	default:
		fail("operação desconhecida: " + p.Op)
	}
	t0 := time.Now()
	resp, err := client.Do(req)
	if err != nil {
		return sample{ns: time.Since(t0).Nanoseconds(), note: "transporte: " + shorten(err.Error())}
	}
	data, rerr := io.ReadAll(resp.Body)
	resp.Body.Close()
	ns := time.Since(t0).Nanoseconds()
	s := sample{ns: ns, status: resp.StatusCode}
	if rerr != nil {
		s.status, s.note = 0, "corpo: "+shorten(rerr.Error())
		return s
	}
	switch p.Op {
	case "redirect":
		loc := resp.Header.Get("Location")
		s.valid = resp.StatusCode == 302 && loc == expectURL
		if !s.valid {
			s.note = fmt.Sprintf("GET → %d, Location %q", resp.StatusCode, shorten(loc))
		}
	case "visits":
		var obj map[string]any
		if resp.StatusCode == 200 && json.Unmarshal(data, &obj) == nil {
			if v, ok := obj["visits"].(float64); ok {
				s.valid, s.visits = true, int(v)
			}
		}
		if !s.valid {
			s.note = fmt.Sprintf("GET /api/links → %d, corpo %q", resp.StatusCode, shorten(string(data)))
		}
	default:
		var obj map[string]any
		if resp.StatusCode == 201 && json.Unmarshal(data, &obj) == nil {
			if code, ok := obj["code"].(string); ok && code != "" {
				s.valid, s.code = true, code
			}
		}
		if !s.valid {
			s.note = fmt.Sprintf("POST → %d, corpo %q", resp.StatusCode, shorten(string(data)))
		}
	}
	return s
}

func summarize(lat []float64) map[string]any {
	if len(lat) == 0 {
		return nil
	}
	sort.Float64s(lat)
	sum := 0.0
	for _, v := range lat {
		sum += v
	}
	pct := func(q float64) float64 { // nearest-rank
		k := int(math.Ceil(q*float64(len(lat)))) - 1
		if k < 0 {
			k = 0
		}
		return round(lat[k], 3)
	}
	return map[string]any{"min": round(lat[0], 3), "p50": pct(0.50), "p90": pct(0.90), "p95": pct(0.95),
		"p99": pct(0.99), "max": round(lat[len(lat)-1], 3), "mean": round(sum/float64(len(lat)), 3), "n": len(lat)}
}

func round(v float64, d int) float64 {
	m := math.Pow(10, float64(d))
	return math.Round(v*m) / m
}

func shorten(s string) string {
	if len(s) > 160 {
		return s[:160] + "…"
	}
	return s
}

func fail(msg string) {
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(2)
}
