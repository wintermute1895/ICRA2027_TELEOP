LATEXMK ?= latexmk
MAIN := main.tex

.PHONY: pdf watch clean distclean overleaf-zip

pdf:
	$(LATEXMK) $(MAIN)

watch:
	$(LATEXMK) -pvc $(MAIN)

clean:
	$(LATEXMK) -c $(MAIN)

distclean:
	$(LATEXMK) -C $(MAIN)
	rm -rf build

overleaf-zip:
	./scripts/export_overleaf.sh
