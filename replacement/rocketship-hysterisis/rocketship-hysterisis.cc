////////////////////////////////////////////
//                                        //
//     SRRIP [Jaleel et al. ISCA' 10]     //
//     Jinchun Kim, cienlux@tamu.edu      //
//                                        //
////////////////////////////////////////////
#include <math.h>
#include <map>
#include "cache.h"


/*

 Common structure defines

*/
#define NUM_CORE 1
#define LLC_WAYS 16
#define MAX_LLC_SETS 2048
// 2-bit RRIP counters or all lines
#define maxRRPV 3
uint32_t rrpv[MAX_LLC_SETS][LLC_WAYS];

// policy selector counter to dynamically select policy
#define MAXPSEL 512
#define PSEL_THRESHOLD (MAXPSEL >> 1)
#define SS 0
#define WS 1
#define WH 2
#define SH 3
uint32_t policy_state;
uint32_t psel;

// debug structures
#define SHIP_PLUS_PLUS 0
#define HAWKEYE 1
uint8_t prev_policy, curr_policy;
uint64_t policy_switches, policy_ping_pong;
uint64_t shippp_sampler_hits, shippp_sampler_misses;
uint64_t hawkeye_sampler_hits, hawkeye_sampler_misses;

/*

 Ship++ specific defines

*/
#define SAT_INC(x, max) (x < max) ? (x + 1): x
#define SAT_DEC(x) (x > 0) ? (x - 1) : x
#define TRUE 1
#define FALSE 0

#define RRIP_OVERRIDE_PERC 0

// The base policy is SRRIP. SHIP needs the following on a per-line basis
uint32_t is_prefetch[MAX_LLC_SETS][LLC_WAYS];
uint32_t fill_core[MAX_LLC_SETS][LLC_WAYS];

// These two are only for sampled sets (we use 64 sets)
#define NUM_LEADER_SETS 64

uint32_t ship_sample[MAX_LLC_SETS];
uint32_t line_reuse[MAX_LLC_SETS][LLC_WAYS];
uint64_t line_sig[MAX_LLC_SETS][LLC_WAYS];

// SHCT. Signature History Counter Table
// per-core 16K entry. 14-bit signature = 16k entry. 3-bit per entry
#define maxSHCTR 7
#define SHIPPP_SHCT_SIZE (1 << 13)
uint32_t SHCT[NUM_CORE][SHIPPP_SHCT_SIZE];

// Statistics
uint64_t insertion_distrib[NUM_TYPES][maxRRPV + 1];
uint64_t total_prefetch_downgrades;


/*

 Hawkeye specific defines

*/
// Per-set timers; we only use 64 of these
// Budget = 64 sets * 1 timer per set * 10 bits per timer = 80 bytes
#define TIMER_SIZE 1024
uint64_t perset_mytimer[MAX_LLC_SETS];

// Signatures for sampled sets; we only use 64 of these
// Budget = 64 sets * 16 ways * 12-bit signature per line = 1.5B
uint64_t signatures[MAX_LLC_SETS][LLC_WAYS];
bool prefetched[MAX_LLC_SETS][LLC_WAYS];

// Hawkeye Predictors for demand and prefetch requests
// Predictor with 2K entries and 5-bit counter per entry
// Budget = 2048*5/8 bytes = 1.2KB
#define MAX_SHCT 31
#define SHCT_SIZE_BITS 11
#define HAWKEYE_SHCT_SIZE (1 << SHCT_SIZE_BITS)
#include "hawkeye_predictor.h"
HAWKEYE_PC_PREDICTOR* demand_predictor;   // Predictor
HAWKEYE_PC_PREDICTOR* prefetch_predictor; // Predictor

#define OPTGEN_VECTOR_SIZE 32
#include "optgen.h"
OPTgen perset_optgen[MAX_LLC_SETS]; // per-set occupancy vectors; we only use 64 of these

#define bitmask(l) (((l) == 64) ? (unsigned long long)(-1LL) : ((1LL << (l)) - 1LL))
#define bits(x, i, l) (((x) >> (i)) & bitmask(l))
// Sample 64 sets per core
#define HAWKEYE_SAMPLE_SET(set, num_sets) (bits(set, 0, 6) == bits(set, ((unsigned long long)log2(num_sets) - 6), 6))
uint32_t hawkeye_sample[MAX_LLC_SETS];
#define SAMPLED_SET(set) (hawkeye_sample[set] == 1)
// Sampler to track 8x cache history for sampled sets
// 2800 entris * 4 bytes per entry = 11.2KB
#define SAMPLED_CACHE_SIZE 2800
#define SAMPLER_WAYS 8
#define SAMPLER_SETS SAMPLED_CACHE_SIZE / SAMPLER_WAYS
vector<map<uint64_t, ADDR_INFO>> addr_history; // Sampler


// initialize ship++ specific structures
void initialize_shippp(uint32_t num_set){
  total_prefetch_downgrades = 0;
  cout << "Initialize SRRIP state" << endl;

  for (int i = 0; i < MAX_LLC_SETS; i++) {
    for (int j = 0; j < LLC_WAYS; j++) {
      rrpv[i][j] = maxRRPV;
      line_reuse[i][j] = FALSE;
      is_prefetch[i][j] = FALSE;
      line_sig[i][j] = 0;
    }
  }

  for (int i = 0; i < NUM_CORE; i++) {
    for (int j = 0; j < SHIPPP_SHCT_SIZE; j++) {
      SHCT[i][j] = 1; // Assume weakly re-use start
    }
  }

  int leaders = 0;
  int tick = 1;
  int interval = num_set/NUM_LEADER_SETS;
  while (leaders < NUM_LEADER_SETS) {
    int set = leaders*interval;
    if(tick){
      ship_sample[set] = 1;
    }
    else{
      ship_sample[set + 1] = 1;
    }
    tick = 1-tick;
    leaders++;
  }
}

// find replacement victim
// return value should be 0 ~ 15 or 16 (bypass)
uint32_t find_victim_shippp(uint32_t cpu, uint64_t instr_id, uint32_t set, const BLOCK* current_set, uint64_t PC, uint64_t paddr, uint32_t type)
{
  // look for the maxRRPV line
  while (1) {
    for (int i = 0; i < LLC_WAYS; i++)
      if (rrpv[set][i] == maxRRPV) { // found victim
        return i;
      }

    for (int i = 0; i < LLC_WAYS; i++)
      rrpv[set][i]++;
  }

  // WE SHOULD NOT REACH HERE
  assert(0);
  return 0;
}

// called on every cache hit and cache fill
void update_replacement_state_shippp(uint32_t cpu, uint32_t set, uint32_t way, uint64_t paddr, uint64_t PC, uint64_t victim_addr, uint32_t type, uint8_t hit)
{
  uint32_t sig = line_sig[set][way];

  if (hit) { // update to REREF on hit
    if (type != WRITEBACK) {

      if ((type == PREFETCH) && is_prefetch[set][way]) {
        //                rrpv[set][way] = 0;

        if ((ship_sample[set] == 1) && (rand() % 100 < 5)) {
          uint32_t fill_cpu = fill_core[set][way];

          SHCT[fill_cpu][sig] = SAT_INC(SHCT[fill_cpu][sig], maxSHCTR);
          line_reuse[set][way] = TRUE;
        }
      } else {
        rrpv[set][way] = 0;

        if (is_prefetch[set][way]) {
          rrpv[set][way] = maxRRPV;
          is_prefetch[set][way] = FALSE;
          total_prefetch_downgrades++;
        }

        if ((ship_sample[set] == 1) && (line_reuse[set][way] == 0)) {
          uint32_t fill_cpu = fill_core[set][way];

          SHCT[fill_cpu][sig] = SAT_INC(SHCT[fill_cpu][sig], maxSHCTR);
          line_reuse[set][way] = TRUE;
        }
      }
    }

    return;
  }

  //--- All of the below is done only on misses -------
  // remember signature of what is being inserted
  uint64_t use_PC = (type == PREFETCH) ? ((PC << 1) + 1) : (PC << 1);
  uint32_t new_sig = use_PC % SHIPPP_SHCT_SIZE;

  if (ship_sample[set] == 1) {
    uint32_t fill_cpu = fill_core[set][way];

    // update signature based on what is getting evicted
    if (line_reuse[set][way] == FALSE) {
      SHCT[fill_cpu][sig] = SAT_DEC(SHCT[fill_cpu][sig]);
    } else {
      SHCT[fill_cpu][sig] = SAT_INC(SHCT[fill_cpu][sig], maxSHCTR);
    }

    line_reuse[set][way] = FALSE;
    line_sig[set][way] = new_sig;
    fill_core[set][way] = cpu;
  }

  is_prefetch[set][way] = (type == PREFETCH);

  // Now determine the insertion prediciton

  uint32_t priority_RRPV = maxRRPV - 1; // default SHIP

  if (type == WRITEBACK) {
    rrpv[set][way] = maxRRPV;
  } else if (SHCT[cpu][new_sig] == 0) {
    rrpv[set][way] = (rand() % 100 >= RRIP_OVERRIDE_PERC) ? maxRRPV : priority_RRPV; // LowPriorityInstallMostly
  } else if (SHCT[cpu][new_sig] == maxSHCTR) {
    rrpv[set][way] = (type == PREFETCH) ? 1 : 0; // HighPriority Install
  } else {
    rrpv[set][way] = priority_RRPV; // HighPriority Install
  }

  // Stat tracking for what insertion it was at
  insertion_distrib[type][rrpv[set][way]]++;
}

string names[] = {"LOAD", "RFO", "PREF", "WRITEBACK"};

// use this function to print out your own stats at the end of simulation
void replacement_final_stats_shippp()
{
  cout << "Insertion Distribution: " << endl;
  /*
  for (uint32_t i = 0; i < NUM_TYPES; i++) {
    cout << "\t" << names[i] << " ";
    for (uint32_t v = 0; v < maxRRPV + 1; v++) {
      cout << insertion_distrib[i][v] << " ";
    }
    cout << endl;
  }
  */
  cout << "Total Prefetch Downgrades: " << total_prefetch_downgrades << endl;
}


///////////////////////////////////////////////
//                                            //
//     Hawkeye [Jain and Lin, ISCA' 16]       //
//     Akanksha Jain, akanksha@cs.utexas.edu  //
//                                            //
///////////////////////////////////////////////


// initialize hawkeye specific structures
void initialize_hawkeye(uint32_t num_set){
  for (int i = 0; i < MAX_LLC_SETS; i++) {
    for (int j = 0; j < LLC_WAYS; j++) {
      rrpv[i][j] = maxRRPV;
      signatures[i][j] = 0;
      prefetched[i][j] = false;
    }
    perset_mytimer[i] = 0;
    perset_optgen[i].init(LLC_WAYS - 2);
  }

  addr_history.resize(SAMPLER_SETS);
  for (int i = 0; i < SAMPLER_SETS; i++)
    addr_history[i].clear();

  demand_predictor = new HAWKEYE_PC_PREDICTOR();
  prefetch_predictor = new HAWKEYE_PC_PREDICTOR();

  int leaders = 0;
  int tick = 0;
  int interval = num_set/NUM_LEADER_SETS;
  while (leaders < NUM_LEADER_SETS) {
    int set = leaders*interval;
    if(tick){
      hawkeye_sample[set] = 1;
    }
    else{
      hawkeye_sample[set + 1] = 1;
    }
    tick = 1-tick;
    leaders++;
  }


  cout << "Initialize Hawkeye state" << endl;
}

// find replacement victim
// return value should be 0 ~ 15 or 16 (bypass)
uint32_t find_victim_hawkeye(uint32_t cpu, uint64_t instr_id, uint32_t set, const BLOCK* current_set, uint64_t PC, uint64_t paddr, uint32_t type)
{
  // look for the maxRRPV line
  for (uint32_t i = 0; i < LLC_WAYS; i++)
    if (rrpv[set][i] == maxRRPV)
      return i;

  // If we cannot find a cache-averse line, we evict the oldest cache-friendly line
  uint32_t max_rrip = 0;
  int32_t lru_victim = -1;
  for (uint32_t i = 0; i < LLC_WAYS; i++) {
    if (rrpv[set][i] >= max_rrip) {
      max_rrip = rrpv[set][i];
      lru_victim = i;
    }
  }

  assert(lru_victim != -1);
  // The predictor is trained negatively on LRU evictions
  if (SAMPLED_SET(set)) {
    if (prefetched[set][lru_victim])
      prefetch_predictor->decrement(signatures[set][lru_victim]);
    else
      demand_predictor->decrement(signatures[set][lru_victim]);
  }
  return lru_victim;

  // WE SHOULD NOT REACH HERE
  assert(0);
  return 0;
}

void replace_addr_history_element(unsigned int sampler_set)
{
  uint64_t lru_addr = 0;

  for (map<uint64_t, ADDR_INFO>::iterator it = addr_history[sampler_set].begin(); it != addr_history[sampler_set].end(); it++) {
    //     uint64_t timer = (it->second).last_quanta;

    if ((it->second).lru == (SAMPLER_WAYS - 1)) {
      // lru_time =  (it->second).last_quanta;
      lru_addr = it->first;
      break;
    }
  }

  addr_history[sampler_set].erase(lru_addr);
}

void update_addr_history_lru(unsigned int sampler_set, unsigned int curr_lru)
{
  for (map<uint64_t, ADDR_INFO>::iterator it = addr_history[sampler_set].begin(); it != addr_history[sampler_set].end(); it++) {
    if ((it->second).lru < curr_lru) {
      (it->second).lru++;
      assert((it->second).lru < SAMPLER_WAYS);
    }
  }
}

// called on every cache hit and cache fill
void update_replacement_state_hawkeye(uint32_t cpu, uint32_t set, uint32_t way, uint64_t paddr, uint64_t PC, uint64_t victim_addr, uint32_t type, uint8_t hit)
{
  paddr = (paddr >> 6) << 6;

  if (type == PREFETCH) {
    if (!hit)
      prefetched[set][way] = true;
  } else
    prefetched[set][way] = false;

  // Ignore writebacks
  if (type == WRITEBACK)
    return;

  // If we are sampling, OPTgen will only see accesses from sampled sets
  if (SAMPLED_SET(set)) {
    // The current timestep
    uint64_t curr_quanta = perset_mytimer[set] % OPTGEN_VECTOR_SIZE;

    uint32_t sampler_set = (paddr >> 6) % SAMPLER_SETS;
    uint64_t sampler_tag = CRC(paddr >> 12) % 256;
    assert(sampler_set < SAMPLER_SETS);

    // This line has been used before. Since the right end of a usage interval is always
    // a demand, ignore prefetches
    if ((addr_history[sampler_set].find(sampler_tag) != addr_history[sampler_set].end()) && (type != PREFETCH)) {
      unsigned int curr_timer = perset_mytimer[set];
      if (curr_timer < addr_history[sampler_set][sampler_tag].last_quanta)
        curr_timer = curr_timer + TIMER_SIZE;
      bool wrap = ((curr_timer - addr_history[sampler_set][sampler_tag].last_quanta) > OPTGEN_VECTOR_SIZE);
      uint64_t last_quanta = addr_history[sampler_set][sampler_tag].last_quanta % OPTGEN_VECTOR_SIZE;
      // and for prefetch hits, we train the last prefetch trigger PC
      if (!wrap && perset_optgen[set].should_cache(curr_quanta, last_quanta)) {
        if (addr_history[sampler_set][sampler_tag].prefetched)
          prefetch_predictor->increment(addr_history[sampler_set][sampler_tag].PC);
        else
          demand_predictor->increment(addr_history[sampler_set][sampler_tag].PC);
      } else {
        // Train the predictor negatively because OPT would not have cached this line
        if (addr_history[sampler_set][sampler_tag].prefetched)
          prefetch_predictor->decrement(addr_history[sampler_set][sampler_tag].PC);
        else
          demand_predictor->decrement(addr_history[sampler_set][sampler_tag].PC);
      }
      // Some maintenance operations for OPTgen
      perset_optgen[set].add_access(curr_quanta);
      update_addr_history_lru(sampler_set, addr_history[sampler_set][sampler_tag].lru);

      // Since this was a demand access, mark the prefetched bit as false
      addr_history[sampler_set][sampler_tag].prefetched = false;
    }
    // This is the first time we are seeing this line (could be demand or prefetch)
    else if (addr_history[sampler_set].find(sampler_tag) == addr_history[sampler_set].end()) {
      // Find a victim from the sampled cache if we are sampling
      if (addr_history[sampler_set].size() == SAMPLER_WAYS)
        replace_addr_history_element(sampler_set);

      assert(addr_history[sampler_set].size() < SAMPLER_WAYS);
      // Initialize a new entry in the sampler
      addr_history[sampler_set][sampler_tag].init(curr_quanta);
      // If it's a prefetch, mark the prefetched bit;
      if (type == PREFETCH) {
        addr_history[sampler_set][sampler_tag].mark_prefetch();
        perset_optgen[set].add_prefetch(curr_quanta);
      } else
        perset_optgen[set].add_access(curr_quanta);
      update_addr_history_lru(sampler_set, SAMPLER_WAYS - 1);
    } else // This line is a prefetch
    {
      assert(addr_history[sampler_set].find(sampler_tag) != addr_history[sampler_set].end());
      // if(hit && prefetched[set][way])
      uint64_t last_quanta = addr_history[sampler_set][sampler_tag].last_quanta % OPTGEN_VECTOR_SIZE;
      if (perset_mytimer[set] - addr_history[sampler_set][sampler_tag].last_quanta < 5 * NUM_CORE) {
        if (perset_optgen[set].should_cache(curr_quanta, last_quanta)) {
          if (addr_history[sampler_set][sampler_tag].prefetched)
            prefetch_predictor->increment(addr_history[sampler_set][sampler_tag].PC);
          else
            demand_predictor->increment(addr_history[sampler_set][sampler_tag].PC);
        }
      }

      // Mark the prefetched bit
      addr_history[sampler_set][sampler_tag].mark_prefetch();
      // Some maintenance operations for OPTgen
      perset_optgen[set].add_prefetch(curr_quanta);
      update_addr_history_lru(sampler_set, addr_history[sampler_set][sampler_tag].lru);
    }

    // Get Hawkeye's prediction for this line
    bool new_prediction = demand_predictor->get_prediction(PC);
    if (type == PREFETCH)
      new_prediction = prefetch_predictor->get_prediction(PC);
    // Update the sampler with the timestamp, PC and our prediction
    // For prefetches, the PC will represent the trigger PC
    addr_history[sampler_set][sampler_tag].update(perset_mytimer[set], PC, new_prediction);
    addr_history[sampler_set][sampler_tag].lru = 0;
    // Increment the set timer
    perset_mytimer[set] = (perset_mytimer[set] + 1) % TIMER_SIZE;
  }

  bool new_prediction = demand_predictor->get_prediction(PC);
  if (type == PREFETCH)
    new_prediction = prefetch_predictor->get_prediction(PC);

  signatures[set][way] = PC;

  // Set RRIP values and age cache-friendly line
  if (!new_prediction)
    rrpv[set][way] = maxRRPV;
  else {
    rrpv[set][way] = 0;
    if (!hit) {
      bool saturated = false;
      for (uint32_t i = 0; i < LLC_WAYS; i++)
        if (rrpv[set][i] == maxRRPV - 1)
          saturated = true;

      // Age all the cache-friendly  lines
      for (uint32_t i = 0; i < LLC_WAYS; i++) {
        if (!saturated && rrpv[set][i] < maxRRPV - 1)
          rrpv[set][i]++;
      }
    }
    rrpv[set][way] = 0;
  }
}

// use this function to print out your own stats at the end of simulation
void replacement_final_stats_hawkeye()
{
  unsigned int hits = 0;
  unsigned int accesses = 0;
  for (unsigned int i = 0; i < MAX_LLC_SETS; i++) {
    accesses += perset_optgen[i].access;
    hits += perset_optgen[i].get_num_opt_hits();
  }

  std::cout << "OPTgen accesses: " << accesses << std::endl;
  std::cout << "OPTgen hits: " << hits << std::endl;
  std::cout << "OPTgen hit rate: " << 100 * (double)hits / (double)accesses << std::endl;

  cout << endl << endl;
  return;
}

///////////////////////////////////////////////
//                                            //
//     Rocketship                             //
//     Edwin Mascarenhas, emascare@ucsd.edu   //
//                                            //
///////////////////////////////////////////////

// initialize replacement state
void CACHE::initialize_replacement(){
    psel = MAXPSEL/2;
    //assertion to ensure structures are well sized for core LLC sets
    assert(NUM_SET <= MAX_LLC_SETS);
    srand(420);

    initialize_hawkeye(NUM_SET);
    initialize_shippp(NUM_SET);

    prev_policy = WS;
    policy_switches = 0;
    policy_ping_pong = 0;
    policy_state = WS;
}

uint32_t CACHE::find_victim(uint32_t cpu, uint64_t instr_id, uint32_t set, const BLOCK* current_set,
                             uint64_t PC, uint64_t paddr, uint32_t type) {
    // If it is a set that hawkeye is sampling, apply hawkeye policy
    if(SAMPLED_SET(set)){
        return find_victim_hawkeye(cpu, instr_id, set, current_set, PC, paddr, type);
    }

    // If it is set that ship++ is sampling apply ship++ policy
    if(ship_sample[set] == 1){
        return find_victim_shippp(cpu, instr_id, set, current_set, PC, paddr, type);
    }

    // policy for follower sets
    if(policy_state == WH || policy_state == SH){
        return find_victim_hawkeye(cpu, instr_id, set, current_set, PC, paddr, type);
    }
    else{
        assert(policy_state == SS || policy_state == WS);
        return find_victim_shippp(cpu, instr_id, set, current_set, PC, paddr, type);
    }
}

void CACHE::update_replacement_state(uint32_t cpu, uint32_t set, uint32_t way, uint64_t paddr, uint64_t PC,
                                    uint64_t victim_addr, uint32_t type, uint8_t hit){

    // If it is set that hawkeye is sampling apply hawkeye policy
    if(SAMPLED_SET(set)){
        update_replacement_state_hawkeye(cpu, set, way, paddr, PC, victim_addr, type, hit);
        // don't count writeback requests
        if(type == WRITEBACK){
          return;
        }
        if(!hit){
            psel = SAT_DEC(psel);
            hawkeye_sampler_misses++;
        }
        else{
          hawkeye_sampler_hits++;
        }
        return;
    }

    // If it is set that ship++ is sampling apply ship++ policy
    if(ship_sample[set] == 1){
        update_replacement_state_shippp(cpu, set, way, paddr, PC, victim_addr, type, hit);
        // don't count writeback requests
        if(type == WRITEBACK){
          return;
        }
        if(!hit){
            psel = SAT_INC(psel, MAXPSEL);
            shippp_sampler_misses++;
        }
        else{
          shippp_sampler_hits++;
        }
        return;
    }

    // for follower sets
    /*
    Policy switch: 
    If psel counter goes above threshold, policy moves to hawkeye
    If psel counter goes below threshold, policy moves to ship++
    Movement is gradual rather than hard shift. 
    Gradual movement is achieved by policy_state FSM.
    */
    prev_policy = policy_state; 
    switch(policy_state){
      case SS:
        policy_state = (psel>PSEL_THRESHOLD)? WS:SS;
        break;
      case WS:
        policy_state = (psel>PSEL_THRESHOLD)? WH:SS;
        break;
      case WH:
        policy_state = (psel>PSEL_THRESHOLD)? SH:WS;
        break;
      case SH:
        policy_state = (psel>PSEL_THRESHOLD)? SH:WH;
        break;
      default:
        assert(0); // shouldn't reach here
    }
    if(prev_policy == WS && policy_state == WH){
      policy_switches++;
    }

    if(policy_state == WH || policy_state == SH){
        update_replacement_state_hawkeye(cpu, set, way, paddr, PC, victim_addr, type, hit);
    }
    else{
        assert(policy_state == SS || policy_state == WS);
        update_replacement_state_shippp(cpu, set, way, paddr, PC, victim_addr, type, hit);
    }
}


void CACHE::replacement_final_stats(){
    std::cout << "Policy switches:" << policy_switches << std::endl;
    std::cout << "Policy ping-pong:" << policy_ping_pong << std::endl;
    std::cout << "Ship++ sampler hits:" << shippp_sampler_hits << " misses:" << shippp_sampler_misses << std::endl;
    std::cout << "Hawkeye sampler hits:" << hawkeye_sampler_hits << " misses:" << hawkeye_sampler_misses << std::endl;
    replacement_final_stats_hawkeye();
    replacement_final_stats_shippp();
    return;
}