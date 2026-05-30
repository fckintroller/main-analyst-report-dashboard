
    // 등급별 눈이 편안한 시그니처 색상 매핑
    function getRatingColor(rating) {
      if (!rating) return 'var(--text-main)';
      const r = rating.trim();
      if (r.includes('매수') || r.includes('Buy')) return '#10b981'; // 눈이 편안한 에메랄드 그린
      if (r.includes('홀딩') || r.includes('Hold') || r.includes('보유') || r.includes('중립')) return '#d97706'; // 차분하고 눈부심 없는 황금색/노란색
      if (r.includes('매도') || r.includes('Sell') || r.includes('비중축소')) return '#ef4444'; // 무광 로즈 레드
      return 'var(--text-main)';
    }

    // 탭 전환 핸들러
    function switchTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
      });
      document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
      });

      document.getElementById(tabId).classList.add('active');
      event.currentTarget.classList.add('active');

      // 차트 탭 초기화 지연 기동
      if (tabId === 'tab-chart' && !marketChart) {
        setTimeout(initChart, 50);
      }
    }

    // 전역 상태 변수
    let currentDatabase = window.ANALYST_DATABASE || { analysts: [], recommendations: [] };
    let marketChart = null;
    let chartMode = 'pct'; // 'pct' 또는 'price'
    let selectedStocks = ['KOSPI']; // 코스피 기본 선택

    // 화면 로드 즉시 렌더링
    window.addEventListener('DOMContentLoaded', () => {
      renderDashboard();
    });

    function renderDashboard() {
      const analysts = currentDatabase.analysts;
      
      // 투자의견 변동 최신순(역순) 정렬
      const recs = [...currentDatabase.recommendations].sort((a, b) => new Date(b.date) - new Date(a.date));

      // 2. 동적 필터 버튼 바인딩
      const filterButtonsContainer = document.getElementById('filter-buttons');
      filterButtonsContainer.innerHTML = '<button class="filter-btn active" onclick="filterSector(\'ALL\')">전체보기</button>';
      
      const uniqueSectors = [...new Set(analysts.map(a => a.merged_sector))];
      uniqueSectors.forEach(sector => {
        const btn = document.createElement('button');
        btn.className = 'filter-btn';
        btn.innerText = sector;
        btn.setAttribute('onclick', `filterSector('${sector}')`);
        filterButtonsContainer.appendChild(btn);
      });

      // 3. 애널리스트 카드 렌더링
      renderAnalysts(analysts);

      // 4. 의견 변동 알림 테이블 렌더링
      renderAlerts(recs, analysts);

      // 5. 리서치 보고서 렌더링 및 최신순(역순) 정렬
      const reports = [...(currentDatabase.reports || [])].sort((a, b) => new Date(b.date) - new Date(a.date));
      renderReports(reports, analysts);

      // 6. 차트 컨트롤 체크리스트 렌더링
      renderStockChecklist();

      // 7. 경제 캘린더 렌더링
      renderCalendar();

      // 8. 차트 하단 연동 타임라인 렌더링
      renderExternalEvents();
    }

    // 애널리스트 카드 렌더링 함수
    function renderAnalysts(analystList) {
      const container = document.getElementById('analysts-container');
      container.innerHTML = '';

      if (analystList.length === 0) {
        container.innerHTML = '<p style="color:var(--text-sub); text-align:center; grid-column:1/-1;">조건에 부합하는 애널리스트가 없습니다.</p>';
        return;
      }

      analystList.forEach(a => {
        const card = document.createElement('div');
        card.className = 'analyst-card';
        card.setAttribute('data-sector', a.merged_sector);

        const tagsHtml = a.targets.map(t => `<span class="tag">${t}</span>`).join('');

        card.innerHTML = `
          <div>
            <div class="card-header">
              <div class="profile-info">
                <h3>${a.name}</h3>
                <span class="firm-tag">${a.firm}</span>
                <span class="position-tag">${a.position}</span>
              </div>
              <span class="sector-badge">${a.merged_sector}</span>
            </div>
            
            <div class="award-text">
              <i class="fa-solid fa-trophy"></i>
              <span>${a.awards}</span>
            </div>
            
            <p class="evaluation-text">${a.evaluation}</p>
          </div>

          <div>
            <div class="coverage-title">
              <i class="fa-solid fa-chart-line" style="color:var(--accent);"></i>
              <span>대표 커버 기업</span>
            </div>
            <div class="coverage-tags">
              ${tagsHtml}
            </div>
          </div>
        `;
        container.appendChild(card);
      });
    }

    // 섹터 필터 동작 함수
    function filterSector(sectorName) {
      document.querySelectorAll('.filter-btn').forEach(btn => {
        if (btn.innerText === sectorName || (sectorName === 'ALL' && btn.innerText === '전체보기')) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });

      const cards = document.querySelectorAll('.analyst-card');
      cards.forEach(card => {
        const cardSector = card.getAttribute('data-sector');
        if (sectorName === 'ALL' || cardSector === sectorName) {
          card.style.display = 'flex';
          card.style.animation = 'fadeIn 0.2s ease';
        } else {
          card.style.display = 'none';
        }
      });
    }

    // 의견 변동 알림 테이블 렌더링 함수
    function renderAlerts(recs, analysts) {
      const tbody = document.getElementById('alerts-container-body');
      tbody.innerHTML = '';

      if (recs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-sub);">최근 의견 변동 감지 내역이 없습니다.</td></tr>';
        return;
      }

      recs.forEach(r => {
        const analystObj = analysts.find(a => a.id === r.analyst_id) || { name: '외부', firm: '기고', position: '위원' };
        
        const tr = document.createElement('tr');
        
        tr.innerHTML = `
          <td>
            <div class="company-cell">
              <span class="company-name">${r.stock_name}</span>
              <span class="company-code">(${r.stock_code})</span>
            </div>
          </td>
          <td>
            <span style="font-weight:700;">${analystObj.firm} ${analystObj.name}</span>
            <span style="color:var(--text-sub); font-size:0.85rem; margin-left:6px;">${analystObj.position}</span>
          </td>
          <td>
            <span class="badge-alert ${r.change_type === 'upgrade' ? 'upgrade' : 'downgrade'}">${r.change_type === 'upgrade' ? '🟢 상향' : '🔴 하향'}</span>
          </td>
          <td>
            <div class="rating-flow">
              <span style="color:${getRatingColor(r.previous_rating)}; font-weight:700;">${r.previous_rating}</span>
              <i class="fa-solid fa-circle-arrow-right rating-arrow"></i>
              <span style="color:${getRatingColor(r.current_rating)}; font-weight:700;">${r.current_rating}</span>
            </div>
          </td>
          <td class="rating-target">${r.target_price}</td>
          <td class="comment-cell">
            <p class="alert-comment">"${r.comment}"</p>
          </td>
          <td style="color:var(--text-sub);">${r.date}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    // 리서치 보고서 렌더링 함수
    function renderReports(reportList, analysts) {
      const container = document.getElementById('reports-container-grid');
      if (!container) return;
      container.innerHTML = '';

      if (reportList.length === 0) {
        container.innerHTML = '<p style="color:var(--text-sub); text-align:center; grid-column:1/-1;">등록된 보고서가 없습니다.</p>';
        return;
      }

      reportList.forEach(rep => {
        const analystObj = analysts.find(a => a.id === rep.analyst_id) || { name: '외부', firm: '기고', position: '위원' };
        const card = document.createElement('div');
        card.className = 'report-card';

        card.innerHTML = `
          <div>
            <div class="report-card-header">
              <div>
                <h3 class="report-title">${rep.title}</h3>
                <div class="report-meta">
                  <span class="report-author">${analystObj.firm} ${analystObj.name} ${analystObj.position}</span>
                  <span style="margin: 0 4px; color: var(--text-sub);">•</span>
                  <span>${rep.date}</span>
                </div>
              </div>
            </div>
            <p class="report-summary">${rep.summary}</p>
          </div>
          
          <div class="report-footer">
            <div>
              <span style="color:var(--text-sub);">종목: </span>
              <span style="font-weight:700; color:#ffffff;">${rep.stock_name}</span>
            </div>
            <div>
              <span style="color:var(--text-sub);">의견: </span>
              <span style="color:${getRatingColor(rep.rating)}; font-weight:700;">${rep.rating}</span>
            </div>
            <div class="report-target-box">
              <span style="color:var(--text-sub); font-weight:normal; font-size:0.8rem;">목표가: </span>
              <span>${rep.target_price}</span>
            </div>
          </div>
        `;
        container.appendChild(card);
      });
    }

    // 경제 캘린더 렌더링 함수 (그룹화 및 과거 데이터 접기 적용)
    function renderCalendar() {
      const container = document.getElementById('calendar-container-body');
      if (!container) return;
      container.innerHTML = '';
      
      const calendarData = window.CALENDAR_DATA || [];
      
      // 날짜 계산 로직
      const now = new Date();
      now.setHours(0, 0, 0, 0);
      
      function getKorDateStr(d) {
        return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().split('T')[0];
      }
      
      const todayStr = getKorDateStr(now);
      const tomorrow = new Date(now); tomorrow.setDate(tomorrow.getDate() + 1);
      const tomorrowStr = getKorDateStr(tomorrow);

      const dayOfWeek = now.getDay();
      const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
      
      const thisWeekStart = new Date(now); thisWeekStart.setDate(now.getDate() + diffToMonday);
      const thisWeekEnd = new Date(thisWeekStart); thisWeekEnd.setDate(thisWeekStart.getDate() + 6);
      const twStartStr = getKorDateStr(thisWeekStart);
      const twEndStr = getKorDateStr(thisWeekEnd);

      const nextWeekStart = new Date(thisWeekEnd); nextWeekStart.setDate(thisWeekEnd.getDate() + 1);
      const nextWeekEnd = new Date(nextWeekStart); nextWeekEnd.setDate(nextWeekStart.getDate() + 6);
      const nwStartStr = getKorDateStr(nextWeekStart);
      const nwEndStr = getKorDateStr(nextWeekEnd);

      const lastWeekEnd = new Date(thisWeekStart); lastWeekEnd.setDate(lastWeekEnd.getDate() - 1);
      const lastWeekStart = new Date(lastWeekEnd); lastWeekStart.setDate(lastWeekStart.getDate() - 6);
      const lwStartStr = getKorDateStr(lastWeekStart);
      const lwEndStr = getKorDateStr(lastWeekEnd);

      const groups = [
        { id: '과거', title: '⏳ 과거 (지난주 이전)', isPast: true, events: [] },
        { id: '지난주', title: '⬅️ 지난주', isPast: true, events: [] },
        { id: '오늘', title: '📌 오늘', isPast: false, events: [] },
        { id: '내일', title: '🚀 내일', isPast: false, events: [] },
        { id: '이번주', title: '📅 이번 주', isPast: false, events: [] },
        { id: '다음주', title: '🗓️ 다음 주', isPast: false, events: [] },
        { id: '이번달', title: '📆 이번 달 (이후)', isPast: false, events: [] }
      ];

      calendarData.forEach(event => {
        const d = event.date;
        if (d < lwStartStr) {
          groups[0].events.push(event);
        } else if (d >= lwStartStr && d <= lwEndStr) {
          groups[1].events.push(event);
        } else if (d === todayStr) {
          groups[2].events.push(event);
        } else if (d === tomorrowStr) {
          groups[3].events.push(event);
        } else if (d >= twStartStr && d <= twEndStr && d !== todayStr && d !== tomorrowStr) {
          groups[4].events.push(event);
        } else if (d >= nwStartStr && d <= nwEndStr) {
          groups[5].events.push(event);
        } else {
          groups[6].events.push(event);
        }
      });

      groups.forEach(group => {
        const groupContainer = document.createElement('div');
        groupContainer.style.marginBottom = '20px';
        
        let contentHtml = '';
        if (group.events.length === 0) {
          contentHtml = `<div style="color: var(--text-sub); font-size: 0.85rem; padding: 12px; background: rgba(31, 41, 55, 0.4); border-radius: 6px; text-align: center; border: 1px dashed #374151;">일정 없음</div>`;
        } else {
          contentHtml = group.events.map(event => {
            let resultHtml = '';
            if (event.forecast || event.previous) {
              const isPastEvent = event.date < todayStr;
              const fText = event.forecast ? `예상: ${event.forecast}` : '';
              const pText = event.previous ? `이전: ${event.previous}` : '';
              const joined = [fText, pText].filter(x => x).join(' | ');
              
              if (joined) {
                resultHtml = `<div style="font-size: 0.8rem; color: ${isPastEvent ? '#facc15' : '#9ca3af'}; margin-top: 4px; font-weight: ${isPastEvent ? '600' : '400'};">
                                ${isPastEvent ? '✅ 결과치(예측/이전): ' : '📉 예측/이전: '}${joined}
                              </div>`;
              }
            }
            
            return `
              <div style="display: flex; align-items: center; gap: 15px; padding: 12px 15px; border-bottom: 1px solid #101620;">
                <div style="color: #e2e8f0; font-weight: 600; width: 100px;">${event.date}</div>
                <div>
                  <span style="background: rgba(4, 120, 87, 0.15); color: #10b981; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem;">
                    ${event.country}
                  </span>
                </div>
                <div style="color: #ffffff; font-weight: 500; flex: 1;">
                  ${event.title}
                  ${resultHtml}
                </div>
              </div>
            `;
          }).join('');
        }
        
        const headerColor = group.isPast ? '#9ca3af' : '#10b981';
        
        if (group.isPast) {
          groupContainer.innerHTML = `
            <details>
              <summary style="font-size: 1rem; font-weight: 700; color: ${headerColor}; cursor: pointer; padding-bottom: 6px; border-bottom: 1px solid #1f2937; outline: none; transition: var(--transition);">
                ${group.title} <span style="font-size: 0.85rem; font-weight: 400; color: var(--text-sub);">(${group.events.length}건)</span>
              </summary>
              <div style="margin-top: 12px;">
                ${contentHtml}
              </div>
            </details>
          `;
        } else {
          groupContainer.innerHTML = `
            <div style="font-size: 1rem; font-weight: 700; color: ${headerColor}; margin-bottom: 10px; border-bottom: 1px solid #1f2937; padding-bottom: 6px;">
              ${group.title}
            </div>
            <div>
              ${contentHtml}
            </div>
          `;
        }
        
        container.appendChild(groupContainer);
      });
    }

    // 차트 하단 연동 타임라인 렌더링 함수
    function renderExternalEvents() {
      const container = document.getElementById('external-events-list');
      if (!container) return;
      container.innerHTML = '';
      
      const calendarData = window.CALENDAR_DATA || [];
      const todayStr = new Date().toISOString().split('T')[0];
      
      let hasEvents = false;
      calendarData.forEach(event => {
        hasEvents = true;
        
        const item = document.createElement('div');
        item.className = 'external-event-item';
        item.setAttribute('data-date', event.date);
        
        // 결과(예상/이전) HTML 생성
        let resultHtml = '';
        if (event.forecast || event.previous) {
          const isPast = event.date < todayStr;
          const fText = event.forecast ? `예상: ${event.forecast}` : '';
          const pText = event.previous ? `이전: ${event.previous}` : '';
          const joined = [fText, pText].filter(x => x).join(' | ');
          
          if (joined) {
            resultHtml = `<div style="font-size: 0.8rem; color: ${isPast ? '#facc15' : '#9ca3af'}; margin-top: 4px; font-weight: ${isPast ? '600' : '400'};">
                            ${isPast ? '✅ 결과치(예측/이전): ' : '📉 예측/이전: '}${joined}
                          </div>`;
          }
        }
        
        item.innerHTML = `
          <div class="event-date" style="color: #e2e8f0; font-weight: 600; width: 90px;">${event.date}</div>
          <div>
            <span style="background: rgba(4, 120, 87, 0.15); color: #10b981; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem;">
              ${event.country}
            </span>
          </div>
          <div class="event-title" style="color: #ffffff; font-weight: 500; flex: 1;">
            ${event.title}
            ${resultHtml}
          </div>
        `;
        container.appendChild(item);
      });
      
      if (!hasEvents) {
        container.innerHTML = '<p style="color:var(--text-sub); text-align:center; padding: 20px;">예정된 경제 일정이 없습니다.</p>';
      }
    }

    function renderIrEvents() {
      const container = document.getElementById('ir-events-list');
      const header = document.getElementById('ir-events-header');
      if (!container || !header) return;
      
      const hasKospi = selectedStocks.includes('KOSPI');
      const isSingleStockSelected = !hasKospi && selectedStocks.length === 1;
      
      if (!isSingleStockSelected) {
        header.innerText = '🏢 개별 종목 IR 공시';
        container.innerHTML = '<div style="color: var(--text-sub); font-size: 0.8rem; text-align: center; padding: 20px;">코스피(KOSPI) 체크를 해제하고, 단일 종목을 선택하시면 해당 종목의 IR 공시 내역이 나타납니다.</div>';
        return;
      }
      
      const stockName = selectedStocks[0];
      header.innerText = `🏢 ${stockName} IR 공시`;
      const irData = (window.IR_DATA && window.IR_DATA[stockName]) ? window.IR_DATA[stockName] : [];
      
      container.innerHTML = '';
      if (irData.length === 0) {
        container.innerHTML = '<p style="color:var(--text-sub); text-align:center; padding: 20px;">수집된 IR 공시 내역이 없습니다.</p>';
        return;
      }
      
      irData.forEach(event => {
        const item = document.createElement('div');
        item.className = 'external-event-item';
        item.setAttribute('data-date', event.date);
        
        item.innerHTML = `
          <div class="event-date" style="color: #e2e8f0; font-weight: 600; width: 90px;">${event.date}</div>
          <div class="event-title" style="color: #ffffff; font-weight: 500; flex: 1;">
            ${event.title}
          </div>
        `;
        container.appendChild(item);
      });
    }

    // Chart.js 초기화 함수
    function initChart() {
      const ctx = document.getElementById('marketChart').getContext('2d');
      const marketData = window.MARKET_DATA || { dates: [], series: {} };
      
      const config = {
        type: 'line',
        data: {
          labels: marketData.dates,
          datasets: []
        },
        options: {
          onHover: (e, activeElements, chart) => {
            if (!chart.scales.x) return;
            const xValue = chart.scales.x.getValueForPixel(e.x);
            
            // 모든 리스트 하이라이트 해제
            document.querySelectorAll('.external-event-item').forEach(el => {
              el.classList.remove('highlighted-event');
            });
            let needsUpdate = false;
            const annotations = chart.options.plugins.annotation?.annotations || {};

            if (xValue >= 0 && xValue < chart.data.labels.length) {
              const hoveredDate = chart.data.labels[xValue];
              
              let firstScrolled = false;
              
              // 차트 세로선 하이라이트 및 말풍선 툴팁 표시
              for (const key in annotations) {
                const ann = annotations[key];
                if (!ann.original) {
                  ann.original = { 
                    borderColor: ann.borderColor, 
                    borderWidth: ann.borderWidth,
                    labelDisplay: ann.label?.display
                  };
                }
                
                if (ann.xMin === hoveredDate) {
                  if (ann.borderColor !== 'rgba(250, 204, 21, 1)') {
                    ann.borderColor = 'rgba(250, 204, 21, 1)';
                    ann.borderWidth = 3;
                    if (ann.label) ann.label.display = true;
                    needsUpdate = true;
                  }
                  
                  // 하단 리스트 하이라이트 연동 (originalDate 기준 매칭)
                  const originalDate = ann.originalDate || hoveredDate;
                  const targetEl = document.querySelector(`.external-event-item[data-date="${originalDate}"]`);
                  if (targetEl) {
                    targetEl.classList.add('highlighted-event');
                    if (!firstScrolled) {
                      targetEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                      firstScrolled = true;
                    }
                  }
                } else {
                  if (ann.borderColor === 'rgba(250, 204, 21, 1)') {
                    ann.borderColor = ann.original.borderColor;
                    ann.borderWidth = ann.original.borderWidth;
                    if (ann.label) ann.label.display = ann.original.labelDisplay;
                    needsUpdate = true;
                  }
                }
              }
            } else {
               // 마우스가 차트 밖일 때
               for (const key in annotations) {
                 const ann = annotations[key];
                 if (ann && ann.original && ann.borderColor === 'rgba(250, 204, 21, 1)') {
                    ann.borderColor = ann.original.borderColor;
                    ann.borderWidth = ann.original.borderWidth;
                    if (ann.label) ann.label.display = ann.original.labelDisplay;
                    needsUpdate = true;
                 }
               }
            }
            if (needsUpdate) chart.update('none');
          },
          responsive: true,
          maintainAspectRatio: false,
          layout: {
            padding: {
              top: 80 // 말풍선 팝업이 차트 상단 밖으로 벗어나도 잘리지 않도록 충분한 상단 여백 확보
            }
          },
          interaction: {
            mode: 'index',
            intersect: false
          },
          plugins: {
            legend: {
              display: true,
              position: 'top',
              labels: {
                color: '#e2e8f0',
                font: {
                  family: 'Inter',
                  size: 11
                }
              }
            },
            tooltip: {
              backgroundColor: '#080c12',
              titleColor: '#10b981',
              bodyColor: '#e2e8f0',
              borderColor: '#101620',
              borderWidth: 1,
              padding: 12,
              titleFont: { weight: 'bold' }
            }
          },
          scales: {
            x: {
              grid: {
                color: '#101620',
                borderColor: '#101620'
              },
              ticks: {
                color: '#9ca3af',
                font: { size: 10 }
              }
            },
            y: {
              type: 'linear',
              display: true,
              position: 'left',
              grid: {
                color: '#101620',
                borderColor: '#101620'
              },
              ticks: {
                color: '#9ca3af',
                font: { size: 10 }
              }
            }
          }
        }
      };

      marketChart = new Chart(ctx, config);
      updateChart();
    }

    // 차트 동적 업데이트 함수
    function updateChart() {
      if (!marketChart) return;
      
      renderIrEvents(); // IR 패널 동적 갱신
      
      const marketData = window.MARKET_DATA || { dates: [], series: {} };
      const datasets = [];

      const colors = {
        'KOSPI': '#10b981',
        'SK하이닉스': '#06b6d4',
        '삼성전자': '#3b82f6',
        '삼양식품': '#f59e0b',
        '알테오젠': '#ec4899',
        '한화에어로스페이스': '#f97316',
        '한국전력': '#a855f7',
        '에코프로비엠': '#84cc16'
      };
      
      const defaultColors = ['#06b6d4', '#f59e0b', '#ec4899', '#f97316', '#a855f7', '#84cc16', '#3b82f6', '#14b8a6', '#6366f1'];
      let colorIndex = 0;

      const hasKospi = selectedStocks.includes('KOSPI');
      const hasOther = selectedStocks.some(s => s !== 'KOSPI');

      let yTitleText = chartMode === 'pct' ? '누적 수익률 (%)' : '주가 (KRW)';
      if (!hasOther && hasKospi) {
          yTitleText = '코스피 지수 (PT)';
      }

      const scales = {
        x: marketChart.options.scales.x,
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          grid: { color: '#101620' },
          ticks: {
            color: '#9ca3af',
            callback: function(value) {
              if (!hasOther && hasKospi) return value.toLocaleString() + ' pt';
              return chartMode === 'pct' ? value.toFixed(1) + '%' : value.toLocaleString();
            }
          },
          title: {
            display: true,
            text: yTitleText,
            color: '#e2e8f0'
          }
        }
      };
      
      if (hasKospi && hasOther) {
        scales.y2 = {
          type: 'linear',
          display: true,
          position: 'right',
          grid: { drawOnChartArea: false },
          ticks: { 
            color: '#10b981',
            callback: function(value) { return value.toLocaleString() + ' pt'; }
          },
          title: {
            display: true,
            text: '코스피 지수 (PT)',
            color: '#10b981'
          }
        };
      } else {
        if (marketChart.options.scales.y2) {
          delete marketChart.options.scales.y2;
        }
      }

      // 미래 30일치 날짜 패딩 생성 (차트 오른쪽 빈 공간 확보)
      const today = new Date();
      const todayStr = today.toISOString().split('T')[0];
      const paddedDates = [...marketData.dates];
      let lastDate = new Date(paddedDates[paddedDates.length - 1]);
      if (isNaN(lastDate)) lastDate = today;
      
      for (let i = 1; i <= 30; i++) {
        const nextDate = new Date(lastDate);
        nextDate.setDate(nextDate.getDate() + i);
        paddedDates.push(nextDate.toISOString().split('T')[0]);
      }
      
      marketChart.data.labels = paddedDates;

      selectedStocks.forEach(stock => {
        const seriesData = marketData.series[stock];
        if (!seriesData) return;

        let finalData = [];
        if (chartMode === 'pct' && stock !== 'KOSPI') {
          const base = seriesData[0];
          finalData = seriesData.map(p => base === 0 ? 0 : ((p - base) / base) * 100);
        } else {
          finalData = seriesData;
        }

        // 미래 날짜만큼 null을 채워서 선이 오늘까지만 그려지게 함
        const paddedSeriesData = [...finalData];
        for (let i = 0; i < 30; i++) paddedSeriesData.push(null);

        const color = colors[stock] || defaultColors[colorIndex++ % defaultColors.length];
        
        datasets.push({
          label: stock,
          data: paddedSeriesData,
          borderColor: color,
          backgroundColor: color + '15',
          borderWidth: stock === 'KOSPI' ? 2.5 : 2,
          pointRadius: 1,
          pointHoverRadius: 4,
          tension: 0.15,
          yAxisID: (stock === 'KOSPI' && hasOther) ? 'y2' : 'y'
        });
      });

      // 캘린더 이벤트 미래 일정만 차트 하단 말풍선(Neon Yellow)으로 표시
      const hasKospi = selectedStocks.includes('KOSPI');
      const isSingleStockSelected = !hasKospi && selectedStocks.length === 1;
      
      let sourceData = window.CALENDAR_DATA || [];
      if (isSingleStockSelected) {
        const stockName = selectedStocks[0];
        sourceData = (window.IR_DATA && window.IR_DATA[stockName]) ? window.IR_DATA[stockName] : [];
      }
      
      const annotations = {};
      
      if (typeof window['chartjs-plugin-annotation'] !== 'undefined') {
        Chart.register(window['chartjs-plugin-annotation']);
      }
      
      // 1. 날짜별 그룹화 (주말/휴일 등 차트 X축에 없는 날짜는 가장 가까운 날짜로 매핑하여 묶음)
      const groupedEvents = {};
      sourceData.forEach((ev) => {
        let matchDate = ev.date;
        if (!paddedDates.includes(matchDate)) {
           const targetTime = new Date(matchDate).getTime();
           let closest = paddedDates[0];
           let minDiff = Infinity;
           paddedDates.forEach(d => {
             const diff = Math.abs(new Date(d).getTime() - targetTime);
             if (diff < minDiff) {
               minDiff = diff;
               closest = d;
             }
           });
           matchDate = closest;
        }
        
        if (!groupedEvents[matchDate]) {
          groupedEvents[matchDate] = [];
        }
        groupedEvents[matchDate].push({ ...ev, originalDate: ev.date });
      });

      // 2. 어노테이션 렌더링 (날짜 당 1개만 생성하여 말풍선 겹침 원천 차단)
      let futureEventIndex = 0;
      Object.keys(groupedEvents).forEach(matchDate => {
        const eventsForDate = groupedEvents[matchDate];
        const isPast = eventsForDate[0].originalDate < todayStr;
        
        const contentArr = [];
        eventsForDate.forEach((ev, idx) => {
          let labelContent = `[${ev.country}] ${ev.title}`;
          let subText = '';
          if (ev.forecast || ev.previous) {
            subText = isPast 
              ? `  결과: 예상 ${ev.forecast} | 이전 ${ev.previous}` 
              : `  예측: 예상 ${ev.forecast} | 이전 ${ev.previous}`;
          }
          
          contentArr.push(labelContent);
          if (subText) contentArr.push(subText);
          if (idx < eventsForDate.length - 1) contentArr.push(''); // 이벤트 간 빈 줄 추가
        });
        
        annotations[`event_${futureEventIndex}`] = {
          type: 'line',
          xMin: matchDate,
          xMax: matchDate,
          originalDate: eventsForDate[0].originalDate, // 하단 리스트 연동용
          borderColor: isPast ? 'rgba(156, 163, 175, 0.2)' : 'rgba(250, 204, 21, 0.2)', // 과거는 회색, 미래는 네온옐로우
          borderWidth: 1.5,
          borderDash: [3, 3],
          label: {
            display: false, // 평소에는 숨김 (오버 시 표시)
            content: contentArr,
            position: 'start',
            color: isPast ? '#ffffff' : '#000000',
            backgroundColor: isPast ? 'rgba(75, 85, 99, 0.95)' : 'rgba(250, 204, 21, 0.95)',
            borderRadius: 6,
            font: { size: 10, weight: 'bold' },
            padding: 8,
            yAdjust: -30
          }
        };
        futureEventIndex++;
      });
      
      marketChart.options.plugins.annotation = { 
        clip: false, // 차트 밖(패딩 영역 등)으로 나가도 말풍선이 잘리지 않도록 설정
        annotations: annotations 
      };

      marketChart.options.scales = scales;
      marketChart.data.datasets = datasets;
      marketChart.update();
    }

    // 모드 제어
    function setChartMode(mode) {
      chartMode = mode;
      document.getElementById('btn-chart-mode-pct').classList.toggle('active', mode === 'pct');
      document.getElementById('btn-chart-mode-price').classList.toggle('active', mode === 'price');
      
      const desc = document.getElementById('chart-desc');
      if (mode === 'pct') {
        desc.innerText = '* 2025년 6월 기점을 0%로 가정하고 코스피 대비 개별 종목들의 누적 수익률 추이를 비교 분석합니다.';
      } else {
        desc.innerText = '* 선택한 종목들의 원화(KRW) 실제 주가 추이를 코스피 지수(우측 축)와 연동하여 비교 분석합니다.';
      }

      updateChart();
    }

    // 우측 컨트롤 체크리스트 빌더
    function renderStockChecklist() {
      const container = document.getElementById('stock-checklist');
      if (!container) return;
      container.innerHTML = '';

      const marketData = window.MARKET_DATA || { dates: [], series: {} };
      const stocks = Object.keys(marketData.series);
      const sortedStocks = ['KOSPI', ...stocks.filter(s => s !== 'KOSPI').sort()];

      sortedStocks.forEach(stock => {
        const seriesData = marketData.series[stock];
        const currentPrice = seriesData[seriesData.length - 1];
        
        let priceStr = '';
        if (stock === 'KOSPI') {
          priceStr = currentPrice.toLocaleString() + ' pt';
        } else {
          priceStr = currentPrice.toLocaleString() + ' 원';
        }

        const isChecked = selectedStocks.includes(stock);
        const item = document.createElement('label');
        item.className = 'stock-item-label';
        item.style.cssText = "display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border: 1px solid var(--card-border); border-radius: 6px; background: #080c12; cursor: pointer; transition: var(--transition); user-select: none;";
        item.setAttribute('data-stock-name', stock);
        
        item.innerHTML = `
          <div style="display: flex; align-items: center; gap: 10px;">
            <input type="checkbox" class="stock-chk" value="${stock}" ${isChecked ? 'checked' : ''} onchange="handleStockCheck(this)" style="accent-color: var(--primary); cursor: pointer;">
            <span style="font-size: 0.88rem; font-weight: ${stock === 'KOSPI' ? '700' : '500'}; color: ${stock === 'KOSPI' ? '#10b981' : '#ffffff'};">${stock}</span>
          </div>
          <span style="font-size: 0.8rem; color: var(--text-sub);">${priceStr}</span>
        `;

        if (isChecked) {
          item.style.borderColor = 'rgba(4, 120, 87, 0.4)';
          item.style.background = 'rgba(4, 120, 87, 0.04)';
        }

        container.appendChild(item);
      });
    }

    // 종목 체크 핸들러
    function handleStockCheck(chk) {
      const stock = chk.value;
      const label = chk.closest('.stock-item-label');
      
      if (chk.checked) {
        if (!selectedStocks.includes(stock)) {
          selectedStocks.push(stock);
        }
        label.style.borderColor = 'rgba(4, 120, 87, 0.4)';
        label.style.background = 'rgba(4, 120, 87, 0.04)';
      } else {
        selectedStocks = selectedStocks.filter(s => s !== stock);
        label.style.borderColor = 'var(--card-border)';
        label.style.background = '#080c12';
      }
      
      updateChart();
    }

    // 체크리스트 검색 필터
    function filterStockChecklist() {
      const query = document.getElementById('stock-search').value.toLowerCase().trim();
      const labels = document.querySelectorAll('.stock-item-label');

      labels.forEach(label => {
        const name = label.getAttribute('data-stock-name').toLowerCase();
        if (name === 'kospi' || name.includes(query)) {
          label.style.display = 'flex';
        } else {
          label.style.display = 'none';
        }
      });
    }

    // 전체 선택/해제
    function toggleAllStocks(select) {
      const chks = document.querySelectorAll('.stock-chk');
      selectedStocks = ['KOSPI'];

      chks.forEach(chk => {
        const stock = chk.value;
        if (stock === 'KOSPI') return;

        chk.checked = select;
        const label = chk.closest('.stock-item-label');
        if (select) {
          selectedStocks.push(stock);
          label.style.borderColor = 'rgba(4, 120, 87, 0.4)';
          label.style.background = 'rgba(4, 120, 87, 0.04)';
        } else {
          label.style.borderColor = 'var(--card-border)';
          label.style.background = '#080c12';
        }
      });

      updateChart();
    }
  