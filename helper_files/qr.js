/*
 * qr.js — tiny, dependency-free QR Code encoder.
 *
 * Scope: byte mode, error-correction level M, versions 1–10 (enough for any
 * waze.com/ul share link). Produces a boolean module matrix. Validated for
 * exact-matrix equality against the `segno` reference encoder (see
 * qr_validate.mjs / validation in site_generator's build notes).
 *
 * Works both in the browser (attaches window.qrGenerate) and in Node
 * (module.exports), so the same code that ships is the code that's tested.
 */
(function (root) {
  "use strict";

  // ---- Galois field GF(256), primitive polynomial 0x11d ----
  var EXP = new Array(512);
  var LOG = new Array(256);
  (function initGF() {
    var x = 1;
    for (var i = 0; i < 255; i++) {
      EXP[i] = x;
      LOG[x] = i;
      x <<= 1;
      if (x & 0x100) x ^= 0x11d;
    }
    for (var j = 255; j < 512; j++) EXP[j] = EXP[j - 255];
  })();

  function gfMul(a, b) {
    if (a === 0 || b === 0) return 0;
    return EXP[LOG[a] + LOG[b]];
  }

  // Reed–Solomon generator polynomial of given degree.
  function rsGenPoly(degree) {
    var poly = [1];
    for (var d = 0; d < degree; d++) {
      var next = new Array(poly.length + 1).fill(0);
      for (var i = 0; i < poly.length; i++) {
        next[i] ^= poly[i];
        next[i + 1] ^= gfMul(poly[i], EXP[d]);
      }
      poly = next;
    }
    return poly;
  }

  function rsEncode(data, ecLen) {
    var gen = rsGenPoly(ecLen); // length ecLen+1, monic (gen[0] === 1)
    var res = new Array(ecLen).fill(0);
    for (var i = 0; i < data.length; i++) {
      var factor = data[i] ^ res[0];
      res.shift();
      res.push(0);
      // Subtract factor * gen (excluding the leading 1) from the remainder.
      for (var j = 0; j < ecLen; j++) {
        res[j] ^= gfMul(gen[j + 1], factor);
      }
    }
    return res;
  }

  // ---- Per-version tables (EC level M, versions 1–10) ----
  // dataCodewords, ecPerBlock, and block group layout [[numBlocks, dataPerBlock], ...]
  // Versions 1–6 (EC level M). Byte capacity at v6 is 108 bytes — far beyond
  // any waze.com/ul link (~61 bytes) — and v1–6 carry no version-info block,
  // which keeps the encoder small and easy to verify.
  var VERSIONS = {
    1:  { data: 16,  ec: 10, groups: [[1, 16]] },
    2:  { data: 28,  ec: 16, groups: [[1, 28]] },
    3:  { data: 44,  ec: 26, groups: [[1, 44]] },
    4:  { data: 64,  ec: 18, groups: [[2, 32]] },
    5:  { data: 86,  ec: 24, groups: [[2, 43]] },
    6:  { data: 108, ec: 16, groups: [[4, 27]] }
  };
  var MAX_VERSION = 6;

  // Canonical alignment-pattern centre coordinates per version.
  var ALIGN = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34]
  };

  // Remainder bits appended after the final codeword, per version.
  var REMAINDER = { 1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7 };

  // Format-info bit strings (15 bits) for EC level M, mask 0–7. Precomputed
  // with BCH(15,5) + mask XOR 0x5412, per the QR spec.
  var FORMAT_BITS = [
    0x5412, 0x5125, 0x5E7C, 0x5B4B, 0x45F9, 0x40CE, 0x4F97, 0x4AA0
  ];

  function chooseVersion(byteLen) {
    for (var v = 1; v <= MAX_VERSION; v++) {
      var info = VERSIONS[v];
      var cci = 8; // byte-mode char-count indicator is 8 bits for v1–9
      var bitsNeeded = 4 + cci + byteLen * 8;
      if (bitsNeeded <= info.data * 8) return v;
    }
    throw new Error("Data too long for versions 1–6 (byte mode, EC M).");
  }

  function utf8Bytes(str) {
    var out = [];
    for (var i = 0; i < str.length; i++) {
      var c = str.charCodeAt(i);
      if (c < 0x80) out.push(c);
      else if (c < 0x800) {
        out.push(0xC0 | (c >> 6), 0x80 | (c & 0x3F));
      } else if (c >= 0xD800 && c <= 0xDBFF) {
        // surrogate pair
        var c2 = str.charCodeAt(++i);
        var cp = 0x10000 + ((c & 0x3FF) << 10) + (c2 & 0x3FF);
        out.push(0xF0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3F),
                 0x80 | ((cp >> 6) & 0x3F), 0x80 | (cp & 0x3F));
      } else {
        out.push(0xE0 | (c >> 12), 0x80 | ((c >> 6) & 0x3F), 0x80 | (c & 0x3F));
      }
    }
    return out;
  }

  // Build the final interleaved codeword bit array (as 0/1 numbers).
  function buildCodewords(str) {
    var bytes = utf8Bytes(str);
    var version = chooseVersion(bytes.length);
    var info = VERSIONS[version];
    var cci = version <= 9 ? 8 : 16;

    // Bit buffer
    var bits = [];
    function push(val, len) {
      for (var i = len - 1; i >= 0; i--) bits.push((val >> i) & 1);
    }
    push(0b0100, 4);            // byte mode
    push(bytes.length, cci);    // char count
    for (var i = 0; i < bytes.length; i++) push(bytes[i], 8);

    var capacityBits = info.data * 8;
    // Terminator (up to 4 zero bits)
    var term = Math.min(4, capacityBits - bits.length);
    for (var t = 0; t < term; t++) bits.push(0);
    // Padding bits to the next codeword boundary. Matches the reference
    // encoder (segno): extends by (8 - length%8), i.e. a full byte when the
    // stream is already byte-aligned. Harmless (lives in the pad region).
    var padBits = 8 - (bits.length % 8);
    for (var pb = 0; pb < padBits; pb++) bits.push(0);
    // Pad bytes
    var padBytes = [0xEC, 0x11];
    var p = 0;
    while (bits.length < capacityBits) {
      push(padBytes[p % 2], 8);
      p++;
    }

    // Bits -> data codeword bytes
    var dataCw = [];
    for (var b = 0; b < bits.length; b += 8) {
      var v = 0;
      for (var k = 0; k < 8; k++) v = (v << 1) | bits[b + k];
      dataCw.push(v);
    }

    // Split into blocks
    var blocks = [];
    var idx = 0;
    info.groups.forEach(function (g) {
      for (var n = 0; n < g[0]; n++) {
        var dcount = g[1];
        var dcw = dataCw.slice(idx, idx + dcount);
        idx += dcount;
        blocks.push({ data: dcw, ec: rsEncode(dcw, info.ec) });
      }
    });

    // Interleave data codewords
    var result = [];
    var maxData = Math.max.apply(null, blocks.map(function (bl) { return bl.data.length; }));
    for (var col = 0; col < maxData; col++) {
      for (var bl = 0; bl < blocks.length; bl++) {
        if (col < blocks[bl].data.length) result.push(blocks[bl].data[col]);
      }
    }
    // Interleave EC codewords
    for (var ecol = 0; ecol < info.ec; ecol++) {
      for (var bl2 = 0; bl2 < blocks.length; bl2++) {
        result.push(blocks[bl2].ec[ecol]);
      }
    }

    // Codewords -> bit stream + remainder bits
    var finalBits = [];
    for (var c = 0; c < result.length; c++) {
      for (var q = 7; q >= 0; q--) finalBits.push((result[c] >> q) & 1);
    }
    for (var r = 0; r < REMAINDER[version]; r++) finalBits.push(0);

    return { bits: finalBits, version: version };
  }

  // ---- Matrix construction ----
  // forceMask (optional): if 0–7, use that mask instead of auto-selecting.
  function makeMatrix(str, forceMask) {
    var built = buildCodewords(str);
    var version = built.version;
    var size = version * 4 + 17;

    var mods = [];      // module colour: null=unset, 0=light, 1=dark
    var reserved = [];  // true = function pattern / reserved (not data)
    for (var i = 0; i < size; i++) {
      mods.push(new Array(size).fill(null));
      reserved.push(new Array(size).fill(false));
    }
    function set(r, c, dark, isFn) {
      mods[r][c] = dark ? 1 : 0;
      if (isFn) reserved[r][c] = true;
    }

    // Finder pattern + separator at (r,c) top-left of 7x7
    function placeFinder(r, c) {
      for (var dr = -1; dr <= 7; dr++) {
        for (var dc = -1; dc <= 7; dc++) {
          var rr = r + dr, cc = c + dc;
          if (rr < 0 || rr >= size || cc < 0 || cc >= size) continue;
          var dark;
          if (dr >= 0 && dr <= 6 && dc >= 0 && dc <= 6) {
            var inner = (dr === 0 || dr === 6 || dc === 0 || dc === 6) ||
                        (dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4);
            dark = inner;
          } else {
            dark = false; // separator ring
          }
          set(rr, cc, dark, true);
        }
      }
    }
    placeFinder(0, 0);
    placeFinder(0, size - 7);
    placeFinder(size - 7, 0);

    // Timing patterns
    for (var t = 8; t < size - 8; t++) {
      var dark = (t % 2 === 0);
      set(6, t, dark, true);
      set(t, 6, dark, true);
    }

    // Alignment patterns
    var centers = ALIGN[version];
    for (var a = 0; a < centers.length; a++) {
      for (var b = 0; b < centers.length; b++) {
        var ar = centers[a], ac = centers[b];
        // Skip if overlapping a finder pattern
        if ((ar <= 8 && ac <= 8) ||
            (ar <= 8 && ac >= size - 9) ||
            (ar >= size - 9 && ac <= 8)) continue;
        for (var dr = -2; dr <= 2; dr++) {
          for (var dc = -2; dc <= 2; dc++) {
            var isDark = Math.max(Math.abs(dr), Math.abs(dc)) !== 1;
            set(ar + dr, ac + dc, isDark, true);
          }
        }
      }
    }

    // Dark module
    set(size - 8, 8, true, true);

    // Format-info module coordinates (two redundant copies of 15 bits).
    // Order matches the QR spec: bit i (i = 0..14) of the format word lands at
    // fmtCells()[i] = [[vRow, vCol], [hRow, hCol]].
    function fmtCells(i) {
      var vr, vc, hr, hc;
      if (i < 6) { vr = i; vc = 8; }
      else if (i < 8) { vr = i + 1; vc = 8; }
      else { vr = size - 15 + i; vc = 8; }
      if (i < 8) { hr = 8; hc = size - 1 - i; }
      else if (i === 8) { hr = 8; hc = 7; }
      else { hr = 8; hc = 14 - i; }
      return [[vr, vc], [hr, hc]];
    }
    for (var fi = 0; fi < 15; fi++) {
      var cells = fmtCells(fi);
      reserved[cells[0][0]][cells[0][1]] = true;
      reserved[cells[1][0]][cells[1][1]] = true;
    }
    // (Versions 1–6 carry no version-info block, so none to reserve.)

    // Place data bits in zigzag
    var bits = built.bits;
    var bitIdx = 0;
    var upward = true;
    for (var colPair = size - 1; colPair > 0; colPair -= 2) {
      if (colPair === 6) colPair = 5; // skip timing column (mutate loop var so
                                      // the -=2 realigns pairs to 5,4 / 3,2 / 1,0)
      var col = colPair;
      for (var rowStep = 0; rowStep < size; rowStep++) {
        var row = upward ? (size - 1 - rowStep) : rowStep;
        for (var dcol = 0; dcol < 2; dcol++) {
          var cc = col - dcol;
          if (reserved[row][cc]) continue;
          var bit = bitIdx < bits.length ? bits[bitIdx] : 0;
          bitIdx++;
          mods[row][cc] = bit;
        }
      }
      upward = !upward;
    }

    // Mask functions
    function maskFn(m, r, c) {
      switch (m) {
        case 0: return (r + c) % 2 === 0;
        case 1: return r % 2 === 0;
        case 2: return c % 3 === 0;
        case 3: return (r + c) % 3 === 0;
        case 4: return (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0;
        case 5: return ((r * c) % 2) + ((r * c) % 3) === 0;
        case 6: return (((r * c) % 2) + ((r * c) % 3)) % 2 === 0;
        case 7: return (((r + c) % 2) + ((r * c) % 3)) % 2 === 0;
      }
    }

    function applyMaskAndFormat(m) {
      // deep copy modules
      var grid = mods.map(function (row) { return row.slice(); });
      for (var r = 0; r < size; r++) {
        for (var c = 0; c < size; c++) {
          if (!reserved[r][c] && maskFn(m, r, c)) grid[r][c] ^= 1;
        }
      }
      // place format info (bit i -> fmtCells(i), both copies)
      var fmt = FORMAT_BITS[m];
      for (var i = 0; i < 15; i++) {
        var bit = (fmt >> i) & 1;
        var cells = fmtCells(i);
        grid[cells[0][0]][cells[0][1]] = bit;
        grid[cells[1][0]][cells[1][1]] = bit;
      }
      return grid;
    }

    function penalty(grid) {
      var score = 0;
      var n = size;
      // Rule 1: runs of >=5 same colour
      for (var r = 0; r < n; r++) {
        var runC = 1, runR = 1;
        for (var c = 1; c < n; c++) {
          if (grid[r][c] === grid[r][c - 1]) { runC++; if (runC === 5) score += 3; else if (runC > 5) score++; }
          else runC = 1;
          if (grid[c][r] === grid[c - 1][r]) { runR++; if (runR === 5) score += 3; else if (runR > 5) score++; }
          else runR = 1;
        }
      }
      // Rule 2: 2x2 blocks
      for (var r2 = 0; r2 < n - 1; r2++) {
        for (var c2 = 0; c2 < n - 1; c2++) {
          var v = grid[r2][c2];
          if (v === grid[r2][c2 + 1] && v === grid[r2 + 1][c2] && v === grid[r2 + 1][c2 + 1]) score += 3;
        }
      }
      // Rule 3: finder-like patterns 1:1:3:1:1 with 4 light
      var pat1 = [1,0,1,1,1,0,1,0,0,0,0];
      var pat2 = [0,0,0,0,1,0,1,1,1,0,1];
      function matches(arr, off, pat) {
        for (var i = 0; i < 11; i++) if (arr[off + i] !== pat[i]) return false;
        return true;
      }
      for (var r3 = 0; r3 < n; r3++) {
        for (var c3 = 0; c3 <= n - 11; c3++) {
          var rowArr = grid[r3];
          if (matches(rowArr, c3, pat1) || matches(rowArr, c3, pat2)) score += 40;
          var colArr = [];
          for (var z = 0; z < 11; z++) colArr.push(grid[c3 + z][r3]);
          if (matches(colArr, 0, pat1) || matches(colArr, 0, pat2)) score += 40;
        }
      }
      // Rule 4: dark proportion
      var dark = 0;
      for (var r4 = 0; r4 < n; r4++) for (var c4 = 0; c4 < n; c4++) dark += grid[r4][c4];
      var pct = (dark * 100) / (n * n);
      var prev = Math.floor(Math.abs(pct - 50) / 5);
      score += prev * 10;
      return score;
    }

    // Choose best mask (or use forced mask for validation)
    var best = null, bestScore = Infinity, bestMask = 0;
    if (forceMask !== undefined && forceMask !== null) {
      best = applyMaskAndFormat(forceMask);
      bestMask = forceMask;
    } else {
      for (var m = 0; m < 8; m++) {
        var g = applyMaskAndFormat(m);
        var s = penalty(g);
        if (s < bestScore) { bestScore = s; best = g; bestMask = m; }
      }
    }

    // Return boolean matrix
    return best.map(function (row) { return row.map(function (v) { return v === 1; }); });
  }

  var api = { generate: makeMatrix, chooseVersion: chooseVersion };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else { root.qrGenerate = makeMatrix; root.QR = api; }
})(typeof window !== "undefined" ? window : this);
