LATEXMK ?= latexmk
MAIN := main.tex

.PHONY: pdf watch clean distclean

pdf:
	$(LATEXMK) $(MAIN)

watch:
	$(LATEXMK) -pvc $(MAIN)

clean:
	$(LATEXMK) -c $(MAIN)

distclean:
	$(LATEXMK) -C $(MAIN)
	rm -rf build
